"""Bounded, local-only VoiceStudio speech relay; no generated audio is saved."""
import asyncio
import json
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import Field, field_validator
from websockets.asyncio.client import connect

from backend.planner_api import LOCAL_ORIGINS
from backend.schemas import RequestModel
from backend.stt import get_stt, session_lock


router = APIRouter(prefix='/api/tts', tags=['local response speech'])
PROFILES = {'JARVIS': 'f0c26d84', 'JARVIS_2': '8f10d4a1'}


class SpeechRequest(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    voice: Literal['JARVIS', 'JARVIS_2'] = 'JARVIS'

    @field_validator('text')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Speech text is empty')
        return value.strip()


async def check_voice(client, voice):
    responses = await asyncio.gather(*(client.get(path) for path in
        ('/health', '/model/status', f'/profiles/{PROFILES[voice]}')))
    for response in responses:
        response.raise_for_status()
    health, model, profile = (response.json() for response in responses)
    if health.get('version') != '0.5.7' or health.get('status') != 'ok':
        raise ValueError('unsupported_voice_studio')
    if model.get('loaded') is not True or model.get('checkpoint') != 'k2-fsa/OmniVoice':
        raise ValueError('load_local_omnivoice_first')
    if profile.get('id') != PROFILES[voice] or profile.get('language') != 'Korean':
        raise ValueError('saved_korean_voice_missing')


async def relay(ws, upstream, request):
    await upstream.send(json.dumps({'text': request.text, 'voice': PROFILES[request.voice],
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
                await check_voice(client, request.voice)
            async with connect('ws://127.0.0.1:3900/ws/tts', proxy=None, open_timeout=5,
                               close_timeout=2, max_size=64000) as upstream:
                await asyncio.wait_for(relay(ws, upstream, request), 300)
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await ws.send_json({'type': 'error', 'message': '로컬 음성 재생을 완료하지 못했습니다. VoiceStudio의 OmniVoice 로드·한국어 프로필·메모리 상태를 확인해 주세요. 자동 재시도하지 않습니다.'})
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        try:
            await ws.close()
        except (RuntimeError, WebSocketDisconnect):
            pass
