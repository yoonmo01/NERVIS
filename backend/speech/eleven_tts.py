"""ElevenLabs response TTS. Configuration checks never make external requests."""
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from dotenv import dotenv_values

from backend.speech.engine import SpeechError

BASE_URL = 'https://api.elevenlabs.io/v1'


def speech_settings():
    values = {**dotenv_values(Path(__file__).resolve().parents[2] / '.env', interpolate=False), **os.environ}
    key = (values.get('ELEVENLABS_API_KEY') or '').strip()
    model = (values.get('ELEVENLABS_MODEL_ID') or 'eleven_v3').strip()
    voice = (values.get('ELEVENLABS_VOICE_ID') or '').strip()
    if not key or not voice:
        raise SpeechError('elevenlabs_not_configured')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', model) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', voice):
        raise SpeechError('tts_invalid_settings')
    return key, model, voice


class ElevenSpeechStream:
    def __init__(self, client, key, model):
        self.client, self.key, self.model = client, key, model
        self.text = self.voice = None

    async def __aiter__(self):
        if not self.text or not self.voice:
            raise SpeechError('tts_invalid_settings')
        try:
            # One full-text conversion; the browser already buffers before playback.
            async with self.client.stream('POST', BASE_URL + '/text-to-speech/' + self.voice,
                    params={'output_format': 'pcm_24000'}, headers={'xi-api-key': self.key},
                    json={'text': self.text, 'model_id': self.model}) as response:
                if response.status_code != 200:
                    raise SpeechError(f'elevenlabs_http_{response.status_code}')
                content_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
                if content_type not in ('audio/pcm', 'audio/x-pcm', 'application/octet-stream'):
                    raise SpeechError('elevenlabs_invalid_audio')
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
                    raise SpeechError('elevenlabs_invalid_audio')
                yield json.dumps({'type': 'done'})
        except httpx.HTTPError:
            raise SpeechError('elevenlabs_connection_failed') from None


class ElevenLabsSpeechEngine:
    backend_id = 'elevenlabs'
    requires_warmup = False

    def client(self):
        return httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10), trust_env=False, follow_redirects=False)

    @asynccontextmanager
    async def stream(self):
        key, model, _ = speech_settings()
        async with self.client() as client:
            yield ElevenSpeechStream(client, key, model)

    async def check_voice(self, client, voice):
        return speech_settings()[2]

    async def refresh(self, client):
        pass

    async def request(self, upstream, text, voice):
        upstream.text, upstream.voice = text, voice
