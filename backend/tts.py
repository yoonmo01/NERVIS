"""Bounded, local-only VoiceStudio speech relay; no generated audio is saved."""
import asyncio
import json
import os
from pathlib import Path
from time import monotonic
from typing import Annotated
from dotenv import dotenv_values

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import Field, field_validator
from websockets.asyncio.client import connect

from backend.planner_api import LOCAL_ORIGINS
from backend.schemas import RequestModel
from backend.stt import get_stt, session_lock


router = APIRouter(prefix='/api/tts', tags=['local response speech'])
ERRORS = {
    'model_missing': 'VoiceStudio에 설치된 OmniVoice 모델을 확인해 주세요. 자동 다운로드하지 않습니다.',
    'model_loading': 'VoiceStudio의 OmniVoice 로드가 완료되지 않았습니다. 앱의 모델 상태를 확인해 주세요.',
    'voice_missing': '설정한 한국어 음성 프로필을 VoiceStudio에서 찾지 못했습니다. 이름과 언어를 확인해 주세요.',
}

class SpeechError(ValueError):
    pass
def configured_voice():
    values = {**dotenv_values(Path(__file__).resolve().parents[1] / '.env', interpolate=False), **os.environ}
    return (values.get('NERVIS_VOICESTUDIO_VOICE') or 'JARVIS').strip()


class SpeechRequest(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator('text')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Speech text is empty')
        return value.strip()


async def check_voice(client, voice):
    responses = await asyncio.gather(*(client.get(path) for path in
        ('/health', '/model/status', '/profiles')))
    for response in responses:
        response.raise_for_status()
    health, model, profiles = (response.json() for response in responses)
    if health.get('version') != '0.5.7' or health.get('status') != 'ok':
        raise ValueError('unsupported_voice_studio')
    matches = [p for p in profiles if p.get('id') == voice or p.get('name') == voice] if isinstance(profiles, list) else []
    if len(matches) != 1 or matches[0].get('language') != 'Korean' or not isinstance(matches[0].get('id'), str):
        raise SpeechError('voice_missing')
    if model.get('loaded') is not True:
        catalog, engines = await asyncio.gather(client.get('/models'), client.get('/engines/tts'))
        catalog.raise_for_status(); engines.raise_for_status()
        if engines.json().get('active') != 'omnivoice' or not any(
            p.get('repo_id') == 'k2-fsa/OmniVoice' and p.get('installed') is True for p in catalog.json().get('models', [])):
            raise SpeechError('model_missing')
        if not model.get('loading'):
            warmup = await client.post('/setup/warmup')
            warmup.raise_for_status()
        until = monotonic() + 60
        for _ in range(120):
            if monotonic() >= until: break
            response = await client.get('/model/status'); response.raise_for_status()
            model = response.json()
            if model.get('loaded') is True or model.get('error'): break
            await asyncio.sleep(.5)
    if model.get('loaded') is not True or model.get('checkpoint') != 'k2-fsa/OmniVoice':
        raise SpeechError('model_loading')
    return matches[0]['id']


async def prepare_voice(ws, client, voice):
    tasks = [asyncio.create_task(check_voice(client, voice)), asyncio.create_task(ws.receive())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if tasks[1] in done:
            raise WebSocketDisconnect()
        return tasks[0].result()
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def relay(ws, upstream, request, voice_id):
    await upstream.send(json.dumps({'text': request.text, 'voice': voice_id,
                                    'language': 'Korean', 'engine': 'omnivoice'}))
    generated = asyncio.Event()
    tasks = []

    async def output():
        sample_rate = None
        total_bytes = 0
        async for message in upstream:
            if isinstance(message, bytes):
                if sample_rate is None or not message or len(message) % 2:
                    raise ValueError('invalid_pcm')
                total_bytes += len(message)
                if total_bytes > sample_rate * 2 * 180:
                    raise ValueError('speech_audio_limit')
                await ws.send_bytes(message)
                continue
            value = json.loads(message)
            if not isinstance(value, dict):
                raise ValueError('invalid_speech_metadata')
            if value.get('type') == 'start':
                rate = value.get('sample_rate')
                if sample_rate is not None or type(rate) is not int or not 8000 <= rate <= 48000 or value.get('channels') != 1 or value.get('format') != 'pcm16':
                    raise ValueError('unsupported_audio_format')
                sample_rate = rate
                await ws.send_json({'type': 'start', 'sample_rate': rate, 'channels': 1, 'format': 'pcm16'})
            elif value.get('type') == 'done':
                if not total_bytes:
                    raise ValueError('empty_speech')
                generated.set()
                await ws.send_json({'type': 'done'})
                return
            elif value.get('type') == 'error':
                raise ValueError('voice_studio_generation_failed')
            # Routing notices contain engine internals and are not reflected.
        raise ValueError('speech_stream_ended_early')

    async def playback_end():
        value = json.loads(await ws.receive_text())
        if value != {'type': 'playback.finished'} or not generated.is_set():
            raise ValueError('invalid_playback_ack')

    try:
        tasks = [asyncio.create_task(output()), asyncio.create_task(playback_end())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@router.websocket('/stream')
async def speech(ws: WebSocket):
    if ws.headers.get('origin') not in LOCAL_ORIGINS or ws.client is None or ws.client.host not in ('127.0.0.1', '::1'):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        raw = await asyncio.wait_for(ws.receive_text(), 10)
        if len(raw) > 16000:
            raise ValueError('speech_request_limit')
        request = SpeechRequest.model_validate_json(raw)
        if session_lock.locked() or get_stt().lock.locked():
            raise ValueError('speech_busy')
        # The same lock keeps STT decoding and TTS generation/playback apart.
        async with session_lock:
            async with httpx.AsyncClient(base_url='http://127.0.0.1:3900', timeout=5, trust_env=False,
                                         follow_redirects=False) as client:
                voice_id = await prepare_voice(ws, client, configured_voice())
            async with connect('ws://127.0.0.1:3900/ws/tts', proxy=None, open_timeout=5,
                               close_timeout=2, max_size=64000) as upstream:
                await asyncio.wait_for(relay(ws, upstream, request, voice_id), 300)
    except WebSocketDisconnect:
        pass
    except Exception as error:
        try:
            code = str(error) if isinstance(error, SpeechError) else 'generation_failed'
            await ws.send_json({'type': 'error', 'code': code, 'message': ERRORS.get(code, '로컬 음성 재생을 완료하지 못했습니다. VoiceStudio 실행·메모리 상태를 확인해 주세요. 자동 재시도하지 않습니다.')})
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        try:
            await ws.close()
        except (RuntimeError, WebSocketDisconnect):
            pass
