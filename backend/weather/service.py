"""Bounded server-side KMA reads; no secrets or request URLs in responses."""
from copy import deepcopy
from datetime import date, datetime, timedelta
import math
import os
from pathlib import Path
import re
from threading import Lock
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from dotenv import dotenv_values
import httpx

ROOT = Path(__file__).resolve().parents[2]
KST = ZoneInfo('Asia/Seoul')
BASE = 'https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/'
# City representative forecast grids, not a user's precise location.
LOCATIONS = {'춘천': (73,134), '서울': (60,127), '부산': (98,76), '인천': (55,124),
             '대전': (67,100), '대구': (89,90), '광주': (58,74), '제주': (52,38)}


def release_times(now):
    observation = (now-timedelta(minutes=45)).replace(minute=0, second=0, microsecond=0)
    cutoff = now-timedelta(minutes=20)
    candidates = [(cutoff-timedelta(days=d)).replace(hour=h,minute=0,second=0,microsecond=0)
                  for d in (0,1) for h in (2,5,8,11,14,17,20,23)]
    return observation, max(t for t in candidates if t <= cutoff)


def number(value, low, high):
    try:
        result = float(value)
        return result if math.isfinite(result) and low <= result <= high else None
    except (ValueError, TypeError):
        return None


def daily_temperatures(items, day):
    values = {'low_c': None, 'high_c': None}
    for row in items or []:
        if row.get('fcstDate') != day.strftime('%Y%m%d') or row.get('category') not in ('TMN', 'TMX'):
            continue
        time = row.get('fcstTime')
        if not isinstance(time, str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3])[0-5][0-9]', time):
            continue
        value = number(row.get('fcstValue'), -100, 70)
        if value is not None:
            values['low_c' if row['category'] == 'TMN' else 'high_c'] = value
    return values


def daily_release(day, latest):
    early = datetime.combine(day, datetime.min.time(), tzinfo=KST).replace(hour=2)
    return early if early <= latest else early - timedelta(hours=3)


class WeatherService:
    def __init__(self, api_key, *, client=None, clock=None, default_location='춘천'):
        self._key = unquote(api_key.strip()) if re.search(r'%[0-9A-Fa-f]{2}',api_key) else api_key.strip()
        self.client = client
        self.clock = clock or (lambda: datetime.now(KST))
        self.default_location = default_location
        self.cache = {}
        self.lock = Lock()

    @classmethod
    def load(cls):
        values = {**dotenv_values(ROOT/'.env', interpolate=False), **os.environ}
        return cls(values.get('NERVIS_KMA_API_KEY') or '',
                   default_location=values.get('NERVIS_WEATHER_LOCATION') or '춘천')

    def _items(self, client, endpoint, base, grid):
        try:
            with client.stream('GET', BASE+endpoint, params={
                'serviceKey':self._key, 'pageNo':1, 'numOfRows':1500, 'dataType':'JSON',
                'base_date':base.strftime('%Y%m%d'), 'base_time':base.strftime('%H%M'),
                'nx':grid[0], 'ny':grid[1]}) as response:
                if response.status_code in (401,403):
                    return None, 'key_rejected'
                if response.status_code != 200:
                    return None, 'provider_unavailable'
                content = bytearray()
                for chunk in response.iter_bytes():
                    content.extend(chunk)
                    if len(content) > 1_000_000:
                        return None, 'invalid_response'
            import json
            value = json.loads(content)['response']
            code = str(value['header']['resultCode'])
            if code in ('30','31','32'):
                return None, 'key_rejected'
            if code != '00':
                return None, 'provider_unavailable'
            items = value['body']['items']['item']
            if not isinstance(items,list) or len(items)>2000 or not all(isinstance(r,dict) and isinstance(r.get('category'),str) for r in items):
                return None, 'invalid_response'
            return items, None
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return None, 'provider_unavailable'

    def get(self, location=None, day: date | None=None):
        now = self.clock().astimezone(KST)
        requested = (location if location is not None else self.default_location).strip()
        place = requested[:-1] if requested.endswith('시') else requested
        day = day or now.date()
        result = {'status':'unavailable', 'location':place, 'date':day.isoformat(),
                  'source':'기상청 단기예보', 'fetched_at':None, 'cached':False,
                  'current':None, 'hourly':[], 'daily':{'low_c':None,'high_c':None, 'basis':'forecast',
                      'low_issued_at':None,'high_issued_at':None}, 'errors':[],
                  'supported_locations':list(LOCATIONS)}
        if place not in LOCATIONS:
            return {**result,'status':'unknown_location','errors':['location_not_supported']}
        if not now.date() <= day <= now.date()+timedelta(days=3):
            return {**result,'status':'date_unavailable','errors':['date_outside_forecast_range']}
        if not self._key:
            return {**result,'status':'not_configured','errors':['weather_key_missing']}
        cache_key = (place, day)
        with self.lock:
            cached = self.cache.get(cache_key)
            if cached and now < cached[0]:
                return {**deepcopy(cached[1]), 'cached':True}
            observation, forecast = release_times(now)
            owned = self.client is None
            client = self.client or httpx.Client(timeout=httpx.Timeout(8,connect=4), trust_env=False,
                                                  follow_redirects=False)
            try:
                key_rejected = False
                if day == now.date():
                    items, error = self._items(client, 'getUltraSrtNcst', observation, LOCATIONS[place])
                    key_rejected = error == 'key_rejected'
                    values = {r.get('category'):r.get('obsrValue') for r in items or []}
                    temperature = number(values.get('T1H'),-100,70)
                    if temperature is not None:
                        result['current'] = {'observed_at':observation.isoformat(), 'temperature_c':temperature,
                            'humidity_pct':number(values.get('REH'),0,100),
                            'rain_mm':number(values.get('RN1'),0,3000),
                            'wind_m_s':number(values.get('WSD'),0,200),
                            'precipitation':{'0':'없음','1':'비','2':'비/눈','3':'눈','5':'빗방울','6':'빗방울/눈날림','7':'눈날림'}.get(str(values.get('PTY')))}
                    else:
                        result['errors'].append('observation_unavailable')
                items, error = (None,'key_rejected') if key_rejected else self._items(client,'getVilageFcst',forecast,LOCATIONS[place])
                daily = daily_temperatures(items, day)
                for name, value in daily.items():
                    if value is not None:
                        result['daily'][name] = value
                        result['daily']['low_issued_at' if name == 'low_c' else 'high_issued_at'] = forecast.isoformat()
                # Latest releases can omit extrema whose forecast time has already passed.
                # Only fill missing fields, with one older release; never retry a failed request.
                earlier = daily_release(day, forecast)
                if items is not None and error is None and day == now.date() and earlier < forecast and any(v is None for v in daily.values()):
                    older_items, older_error = self._items(client, 'getVilageFcst', earlier, LOCATIONS[place])
                    older = daily_temperatures(older_items, day)
                    for name, value in older.items():
                        if result['daily'][name] is None and value is not None:
                            result['daily'][name] = value
                            result['daily']['low_issued_at' if name == 'low_c' else 'high_issued_at'] = earlier.isoformat()
                    key_rejected = key_rejected or older_error == 'key_rejected'
                if items is not None and any(result['daily'][name] is None for name in ('low_c', 'high_c')):
                    result['errors'].append('daily_temperature_unavailable')
                hours = {}
                for row in items or []:
                    if row.get('fcstDate') != day.strftime('%Y%m%d'):
                        continue
                    try:
                        at = datetime.strptime(row['fcstDate']+row['fcstTime'],'%Y%m%d%H%M').replace(tzinfo=KST)
                    except (ValueError,KeyError,TypeError):
                        continue
                    category, value = row.get('category'), row.get('fcstValue')
                    if category not in ('TMP','POP','SKY'):
                        continue
                    if day == now.date() and at < now.replace(minute=0,second=0,microsecond=0):
                        continue
                    entry = hours.setdefault(at.isoformat(),{'at':at.isoformat(),'temperature_c':None,'rain_probability_pct':None,'sky':None})
                    if category == 'TMP': entry['temperature_c'] = number(value,-100,70)
                    elif category == 'POP': entry['rain_probability_pct'] = number(value,0,100)
                    else: entry['sky'] = {'1':'맑음','3':'구름많음','4':'흐림'}.get(str(value))
                result['hourly'] = [hours[k] for k in sorted(hours) if any(hours[k][f] is not None for f in ('temperature_c','rain_probability_pct','sky'))]
                if not result['hourly']:
                    result['errors'].append('forecast_unavailable')
                if key_rejected or error == 'key_rejected':
                    result['errors'].append('weather_key_rejected')
            finally:
                if owned: client.close()
            available = result['current'] is not None or bool(result['hourly']) or any(result['daily'][name] is not None for name in ('low_c', 'high_c'))
            result['status'] = ('partial' if result['errors'] else 'ok') if available else 'unavailable'
            result['fetched_at'] = now.isoformat()
            ttl = 600 if result['status']=='ok' else 60
            self.cache = {k:v for k,v in self.cache.items() if now < v[0]}
            self.cache[cache_key] = (now+timedelta(seconds=ttl),deepcopy(result))
            return result
