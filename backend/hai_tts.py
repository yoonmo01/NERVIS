"""HAI GPT TTS adapter. No discovery, retries, files, or requests during warmup."""
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import dotenv_values

from backend.speech_engine import SpeechError

BASE_URL = 'https://factchat-cloud.mindlogic.ai/v1/gateway'


def speech_settings():
    values = {**dotenv_values(Path(__file__).resolve().parents[1] / '.env', interpolate=False), **os.environ}
    key = values.get('BAZE_API_KEY') or ''
    model = (values.get('NERVIS_TTS_MODEL') or 'gemini-3.1-flash-tts-preview').strip()
    voice = (values.get('NERVIS_TTS_VOICE') or 'Schedar').strip()
    if not key.strip():
        raise SpeechError('tts_not_configured')
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', model) or not re.fullmatch(r'[A-Za-z]{1,64}', voice):
        raise SpeechError('tts_invalid_settings')
    return key, model, voice


class HaiSpeechStream:
    def __init__(self, client, key, model):
        self.client, self.key, self.model = client, key, model
        self.text = self.voice = None

    async def __aiter__(self):
        if not self.text or not self.voice:
            raise SpeechError('tts_invalid_settings')
        try:
            async with self.client.stream('POST', BASE_URL + '/audio/speech/',
                    headers={'Authorization': 'Bearer ' + self.key},
                    json={'model': self.model, 'input': self.text, 'voice': self.voice}) as response:
                if response.status_code != 200:
                    raise SpeechError(f'tts_http_{response.status_code}')
                if 'audio/pcm' not in response.headers.get('content-type', '').lower():
                    raise SpeechError('tts_invalid_audio')
                yield json.dumps({'type': 'start', 'sample_rate': 24000, 'channels': 1, 'format': 'pcm16'})
                total, pending = 0, b''
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > 24000 * 2 * 180:
                        raise SpeechError('tts_audio_limit')
                    pending += chunk
                    size = len(pending) - len(pending) % 2
                    if size:
                        yield pending[:size]
                        pending = pending[size:]
                if not total or pending:
                    raise SpeechError('tts_invalid_audio')
                yield json.dumps({'type': 'done'})
        except httpx.HTTPError:
            raise SpeechError('tts_connection_failed') from None


class HaiGPTSpeechEngine:
    backend_id = 'hai_gpt'
    requires_warmup = False

    def client(self):
        return httpx.AsyncClient(base_url=BASE_URL, timeout=httpx.Timeout(120, connect=10),
                                 trust_env=False, follow_redirects=False)

    @asynccontextmanager
    async def stream(self):
        key, model, _ = speech_settings()
        async with self.client() as client:
            yield HaiSpeechStream(client, key, model)

    async def check_voice(self, client, voice):
        # Configuration-only check: no model list, health, or credit request.
        return speech_settings()[2]

    async def refresh(self, client):
        pass

    async def request(self, upstream, text, voice):
        upstream.text, upstream.voice = text, voice
