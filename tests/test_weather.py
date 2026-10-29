"""Weather tests never read real credentials or contact KMA."""
from datetime import datetime, timedelta
import json
import unittest
from zoneinfo import ZoneInfo
import httpx
from test_analysis import PackageCase


NOW = datetime(2026, 10, 23, 19, 56, tzinfo=ZoneInfo('Asia/Seoul'))


def payload(items):
    return {'response': {'header': {'resultCode': '00'}, 'body': {'items': {'item': items}}}}


def handler(request):
    if request.url.path.endswith('getUltraSrtNcst'):
        return httpx.Response(200, json=payload([{'category': 'T1H', 'obsrValue': '17.3'},
            {'category': 'PTY', 'obsrValue': '0'}, {'category': 'REH', 'obsrValue': '62'}]))
    return httpx.Response(200, json=payload([
        {'category': k, 'fcstDate': '20261023', 'fcstTime': '2000', 'fcstValue': v}
        for k,v in [('TMP','13'),('SKY','1'),('POP','0'),('TMN','5'),('TMX','21')]]))


class WeatherTests(unittest.TestCase):
    def test_missing_extrema_are_filled_once_without_replacing_latest_forecast(self):
        def earlier(request):
            if request.url.path.endswith('getUltraSrtNcst'):
                return handler(request)
            if request.url.params['base_time'] == '0200':
                return httpx.Response(200, json=payload([
                    {'category': category, 'fcstDate': '20261023', 'fcstTime': time, 'fcstValue': value}
                    for category, time, value in [('TMN', '0600', '3'), ('TMX', '1500', '25'), ('TMP', '2000', '1')]]))
            value = handler(request).json()
            value['response']['body']['items']['item'] = [r for r in value['response']['body']['items']['item'] if r['category'] != 'TMN']
            return httpx.Response(200, json=value)
        service = self.service(earlier)
        result = service.get('춘천')
        self.assertEqual(result['daily']['low_c'], 3)
        self.assertEqual(result['daily']['high_c'], 21)
        self.assertEqual(result['daily']['basis'], 'forecast')
        self.assertEqual(result['daily']['low_issued_at'], '2026-10-23T02:00:00+09:00')
        self.assertEqual(result['daily']['high_issued_at'], '2026-10-23T17:00:00+09:00')
        self.assertEqual(result['hourly'][0]['temperature_c'], 13)
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(service.get('춘천')['cached'])
        self.assertEqual(len(self.calls), 3)

    def test_missing_extrema_stay_unknown_and_do_not_use_hourly_minmax(self):
        def missing(request):
            value = handler(request).json()
            if request.url.path.endswith('getVilageFcst'):
                value['response']['body']['items']['item'] = [r for r in value['response']['body']['items']['item'] if r['category'] not in ('TMN', 'TMX')]
            return httpx.Response(200, json=value)
        service = self.service(missing)
        result = service.get('춘천')
        self.assertIsNone(result['daily']['low_c'])
        self.assertIsNone(result['daily']['high_c'])
        self.assertEqual(result['status'], 'partial')
        self.assertIn('daily_temperature_unavailable', result['errors'])
        self.assertEqual(len(self.calls), 3)

    def service(self, fn=handler, key='synthetic-key'):
        from backend.weather import WeatherService
        self.calls=[]
        def wrapped(request):
            self.calls.append(request)
            return fn(request)
        client=httpx.Client(transport=httpx.MockTransport(wrapped))
        self.addCleanup(client.close)
        return WeatherService(key, client=client, clock=lambda:NOW)

    def test_success_cache_units_time_and_no_credentials_in_output(self):
        service=self.service()
        result=service.get('춘천')
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['current']['temperature_c'],17.3)
        self.assertEqual(result['current']['observed_at'],'2026-10-23T19:00:00+09:00')
        self.assertEqual(result['hourly'][0]['rain_probability_pct'],0)
        self.assertEqual(result['hourly'][0]['sky'],'맑음')
        self.assertNotIn('synthetic-key',json.dumps(result))
        self.assertEqual(len(self.calls),2)
        self.assertTrue(service.get('춘천시')['cached'])
        self.assertEqual(len(self.calls),2)
        service.clock=lambda:NOW+timedelta(minutes=11)
        service.get('춘천')
        self.assertEqual(len(self.calls),4)

    def test_release_times_at_midnight_and_early_publish(self):
        from backend.weather import release_times
        obs, forecast=release_times(datetime(2026,10,23,0,10,tzinfo=ZoneInfo('Asia/Seoul')))
        self.assertEqual(obs.strftime('%Y%m%d%H%M'),'202610222300')
        self.assertEqual(forecast.strftime('%Y%m%d%H%M'),'202610222300')
        _, forecast=release_times(datetime(2026,10,23,2,5,tzinfo=ZoneInfo('Asia/Seoul')))
        self.assertEqual(forecast.hour,23)

    def test_bad_key_missing_key_unknown_location_and_old_date(self):
        missing=self.service(key='')
        self.assertEqual(missing.get('춘천')['status'],'not_configured')
        self.assertEqual(len(self.calls),0)
        service=self.service()
        self.assertEqual(service.get('없는도시')['status'],'unknown_location')
        self.assertEqual(service.get('춘천',NOW.date()-timedelta(days=1))['status'],'date_unavailable')
        self.assertEqual(len(self.calls),0)

    def test_partial_failure_cached_and_safe_error(self):
        def partial(request):
            if request.url.path.endswith('getVilageFcst'):
                raise httpx.ReadTimeout('secret-url-content',request=request)
            return handler(request)
        service=self.service(partial)
        result=service.get('춘천')
        self.assertEqual(result['status'],'partial')
        self.assertIsNotNone(result['current'])
        self.assertEqual(result['errors'],['forecast_unavailable'])
        self.assertNotIn('secret-url',json.dumps(result))
        self.assertTrue(service.get('춘천')['cached'])
        self.assertEqual(len(self.calls),2)

    def test_provider_error_and_encoded_key(self):
        service=self.service(lambda _:httpx.Response(200,text='<xml>secret-key</xml>'),key='fake%2Bkey%3D')
        result=service.get('춘천')
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn('secret-key',json.dumps(result))
        self.assertEqual(self.calls[0].url.params['serviceKey'],'fake+key=')

    def test_missing_or_nonfinite_values_do_not_become_measurements(self):
        service=self.service(lambda _:httpx.Response(200,json=payload([{'category':'T1H','obsrValue':'NaN'}])))
        result=service.get('춘천')
        self.assertEqual(result['status'],'unavailable')
        self.assertIsNone(result['current'])

    def test_malformed_category_is_unavailable_not_an_exception(self):
        service=self.service(lambda _:httpx.Response(200,json=payload([{'category':{},'obsrValue':'17'}])))
        self.assertEqual(service.get('춘천')['status'],'unavailable')

    def test_future_weather_has_no_current_observation(self):
        def future(request):
            response=handler(request).json()
            for row in response['response']['body']['items']['item']:
                row['fcstDate']='20261024'
            return httpx.Response(200,json=response)
        service=self.service(future)
        result=service.get('서울',NOW.date()+timedelta(days=1))
        self.assertIsNone(result['current'])
        self.assertEqual(len(self.calls),1)
        self.assertEqual(result['location'],'서울')


class WeatherApiTests(PackageCase):
    def test_partial_weather_keeps_briefing_records_and_uses_shared_cache(self):
        from types import SimpleNamespace
        from fastapi.testclient import TestClient
        from backend.app import create_app
        from backend.weather import WeatherService
        calls=[]
        def partial(request):
            calls.append(request)
            if request.url.path.endswith('getVilageFcst'):
                return httpx.Response(503)
            return handler(request)
        client=httpx.Client(transport=httpx.MockTransport(partial))
        self.addCleanup(client.close)
        weather=WeatherService('synthetic',client=client,clock=lambda:NOW)
        store=SimpleNamespace(daily=lambda day,place:{'classes':[{'name':'synthetic class'}], 'tasks':[{'title':'synthetic task'}]})
        with TestClient(create_app(self.package,planner_store=store,weather_service=weather),base_url='http://127.0.0.1') as api:
            result=api.get('/api/weather?location=춘천').json()
            self.assertEqual(result['status'],'partial')
            briefing=api.get('/api/briefing?date=2026-10-23').json()
            self.assertEqual(briefing['classes'][0]['name'],'synthetic class')
            self.assertEqual(briefing['tasks'][0]['title'],'synthetic task')
            self.assertTrue(briefing['weather']['cached'])
            self.assertEqual(len(calls),2)

    def test_weather_endpoint_needs_no_database_and_rejects_bad_dates(self):
        from fastapi.testclient import TestClient
        from backend.app import create_app
        from backend.weather import WeatherService
        with TestClient(create_app(self.package,weather_service=WeatherService('',clock=lambda:NOW)),base_url='http://127.0.0.1') as api:
            self.assertEqual(api.get('/api/weather').json()['status'],'not_configured')
            self.assertEqual(api.get('/api/weather?date=2026-02-30').status_code,422)
