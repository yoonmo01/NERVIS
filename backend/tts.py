"""Bounded response-speech relay; no generated audio is saved."""
import asyncio
import json
import os
import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID
from dotenv import dotenv_values

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import Field, field_validator, model_validator

from backend.planner_api import LOCAL_ORIGINS
from backend.schemas import RequestModel
from backend.stt import get_stt, session_lock
from backend.speech_engine import SpeechError, get_speech_engine


router = APIRouter(prefix='/api/tts', tags=['local response speech'])
standby_lock = asyncio.Lock()
ERRORS = {
    'elevenlabs_not_configured': 'ELEVENLABS_API_KEY와 ELEVENLABS_VOICE_ID 설정을 확인해 주세요.',
    'elevenlabs_http_400': 'ElevenLabs 모델·목소리·출력 형식 설정을 확인해 주세요.',
    'elevenlabs_http_401': 'ElevenLabs API 키와 사용 가능한 크레딧을 확인해 주세요. 자동 재시도하지 않습니다.',
    'elevenlabs_http_402': 'ElevenLabs 구독·크레딧 한도를 확인해 주세요.',
    'elevenlabs_http_403': 'ElevenLabs 키의 TTS 권한과 목소리 사용 권한을 확인해 주세요.',
    'elevenlabs_http_404': 'ElevenLabs Voice ID와 모델 ID를 확인해 주세요.',
    'elevenlabs_http_422': 'ElevenLabs TTS 모델과 요청 형식 설정을 확인해 주세요.',
    'elevenlabs_http_429': 'ElevenLabs 요청 한도에 도달했습니다. 자동 재시도하지 않습니다.',
    'elevenlabs_connection_failed': 'ElevenLabs 음성 연결에 실패했습니다. 과금됐을 수 있어 자동 재시도하지 않습니다.',
    'elevenlabs_invalid_audio': 'ElevenLabs PCM 음성 응답 형식을 확인하지 못했습니다.',
    'tts_not_configured': 'HAI GPT TTS에 사용할 기존 Gateway 키 설정을 확인해 주세요.',
    'tts_invalid_settings': 'TTS 백엔드·모델·목소리 설정을 확인해 주세요.',
    'tts_http_400': 'HAI GPT TTS 요청 형식이나 모델·목소리 설정을 확인해 주세요.',
    'tts_http_401': 'HAI GPT Gateway 인증을 확인해 주세요.',
    'tts_http_402': 'HAI GPT 크레딧을 확인해 주세요.',
    'tts_http_403': '현재 계정의 HAI GPT TTS 모델 사용 권한을 확인해 주세요.',
    'tts_http_429': 'HAI GPT 요청 한도에 도달했습니다. 자동 재시도하지 않습니다.',
    'tts_connection_failed': 'HAI GPT 음성 연결에 실패했습니다. 이미 과금됐을 수 있어 자동 재시도하지 않습니다.',
    'tts_invalid_audio': 'HAI GPT 음성 응답 형식을 확인하지 못했습니다.',
    'tts_audio_limit': '생성된 음성이 허용 길이 180초를 초과했습니다.',
    'tts_segments_not_supported': '외부 TTS에는 전체 응답을 한 번에 보내 주세요.',
    'model_missing': 'VoiceStudio에 설치된 OmniVoice 모델을 확인해 주세요. 자동 다운로드하지 않습니다.',
    'model_loading': 'VoiceStudio의 OmniVoice 로드가 완료되지 않았습니다. 앱의 모델 상태를 확인해 주세요.',
    'voice_missing': '설정한 한국어 음성 프로필을 VoiceStudio에서 찾지 못했습니다. 이름과 언어를 확인해 주세요.',
}

async def warm_voice():
    if session_lock.locked() or standby_lock.locked() or get_stt().lock.locked():
        return False
    async with standby_lock:
        async with get_speech_engine().client() as client:
            await check_voice(client, configured_voice())
            # get_model refreshes VoiceStudio's idle timer without synthesizing audio.
            await get_speech_engine().refresh(client)
    return True


async def wait_for_standby(ws):
    if not standby_lock.locked():
        return
    async def ready():
        async with standby_lock:
            pass
    tasks = [asyncio.create_task(ready()), asyncio.create_task(ws.receive())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if tasks[1] in done:
            raise WebSocketDisconnect()
        tasks[0].result()
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def maintain_voice():
    if not get_speech_engine().requires_warmup:
        return
    while True:
        await asyncio.sleep(60)
        try:
            await asyncio.wait_for(warm_voice(), 65)
        except Exception:
            logging.getLogger(__name__).warning('Local TTS standby unavailable; check VoiceStudio')


def configured_voice():
    values = {**dotenv_values(Path(__file__).resolve().parents[1] / '.env', interpolate=False), **os.environ}
    return (values.get('NERVIS_VOICESTUDIO_VOICE') or 'JARVIS').strip()


class SpeechRequest(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    segments: Annotated[list[Annotated[str, Field(min_length=1, max_length=2000)]] | None, Field(min_length=1, max_length=12)] = None
    request_id: UUID | None = None
    session_id: UUID | None = None

    @model_validator(mode='after')
    def matching_segments(self):
        if (self.request_id is None) != (self.session_id is None):
            raise ValueError('Speech ownership requires both identifiers')
        if self.segments is not None and (any(not s.strip() for s in self.segments) or
                ' '.join(' '.join(s.split()) for s in self.segments) != ' '.join(self.text.split())):
            raise ValueError('Speech segments must preserve the full text')
        return self

    @field_validator('text')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Speech text is empty')
        return value.strip()


async def check_voice(client, voice):
    return await get_speech_engine().check_voice(client, voice)

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
    owner = {'request_id': str(request.request_id), 'session_id': str(request.session_id)} if request.request_id is not None else {}
    async def send_meta(value):
        await ws.send_json({**value, **owner})
    generated = asyncio.Event()
    tasks = []

    async def output():
        sample_rate = None
        total_bytes = 0
        for index, text in enumerate(request.segments or [request.text]):
            await get_speech_engine().request(upstream, text, voice_id)
            segment_bytes, started = 0, False
            async for message in upstream:
                if isinstance(message, bytes):
                    if not started or not message or len(message) % 2:
                        raise ValueError('invalid_pcm')
                    total_bytes += len(message)
                    segment_bytes += len(message)
                    if total_bytes > sample_rate * 2 * 180:
                        raise ValueError('speech_audio_limit')
                    await ws.send_bytes(message)
                    continue
                value = json.loads(message)
                if not isinstance(value, dict):
                    raise ValueError('invalid_speech_metadata')
                if value.get('type') == 'start':
                    rate = value.get('sample_rate')
                    if started or type(rate) is not int or not 8000 <= rate <= 48000 or value.get('channels') != 1 or value.get('format') != 'pcm16' or (sample_rate is not None and rate != sample_rate):
                        raise ValueError('unsupported_audio_format')
                    if sample_rate is None:
                        await send_meta({'type': 'start', 'sample_rate': rate, 'channels': 1, 'format': 'pcm16'})
                    sample_rate, started = rate, True
                    if request.segments is not None:
                        await send_meta({'type': 'segment', 'index': index})
                elif value.get('type') == 'done':
                    if not segment_bytes:
                        raise ValueError('empty_speech')
                    break
                elif value.get('type') == 'error':
                    raise ValueError('voice_studio_generation_failed')
                # Routing notices contain engine internals and are not reflected.
            else:
                raise ValueError('speech_stream_ended_early')
        generated.set()
        await send_meta({'type': 'done'})

    async def playback_end():
        value = json.loads(await ws.receive_text())
        if value != {'type': 'playback.finished', **owner} or not generated.is_set():
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
    owner = {}
    try:
        raw = await asyncio.wait_for(ws.receive_text(), 10)
        if len(raw) > 16000:
            raise ValueError('speech_request_limit')
        request = SpeechRequest.model_validate_json(raw)
        if request.request_id is not None:
            owner = {'request_id': str(request.request_id), 'session_id': str(request.session_id)}
        if get_speech_engine().backend_id in ('hai_gpt', 'elevenlabs') and request.segments is not None:
            raise SpeechError('tts_segments_not_supported')
        await wait_for_standby(ws)
        if session_lock.locked() or get_stt().lock.locked():
            raise ValueError('speech_busy')
        # The same lock keeps STT decoding and TTS generation/playback apart.
        async with session_lock:
            async with get_speech_engine().client() as client:
                voice_id = await prepare_voice(ws, client, configured_voice())
            async with get_speech_engine().stream() as upstream:
                await asyncio.wait_for(relay(ws, upstream, request, voice_id), 300)
    except WebSocketDisconnect:
        pass
    except Exception as error:
        try:
            code = str(error) if isinstance(error, SpeechError) else 'generation_failed'
            await ws.send_json({'type': 'error', **owner, 'code': code, 'message': ERRORS.get(code, '음성 재생을 완료하지 못했습니다. TTS 설정과 연결 상태를 확인해 주세요. 자동 재시도하지 않습니다.')})
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        try:
            await ws.close()
        except (RuntimeError, WebSocketDisconnect):
            pass
