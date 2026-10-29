"""Speech-engine boundary for local VoiceStudio and explicitly selected HAI GPT."""
import asyncio
import json
import os
from pathlib import Path
from dotenv import dotenv_values
from time import monotonic
from typing import Any, AsyncContextManager, Protocol

import httpx
from websockets.asyncio.client import connect


class SpeechError(ValueError):
    pass


class SpeechEngine(Protocol):
    """Adapters emit start/PCM16/done frames for each requested text segment."""
    backend_id: str
    requires_warmup: bool
    def client(self) -> Any: ...
    def stream(self) -> AsyncContextManager[Any]: ...
    async def check_voice(self, client, voice: str) -> str: ...
    async def refresh(self, client) -> None: ...
    async def request(self, upstream, text: str, voice: str) -> None: ...


class VoiceStudioEngine:
    backend_id = 'voicestudio'
    requires_warmup = True
    def client(self):
        return httpx.AsyncClient(base_url='http://127.0.0.1:3900', timeout=5,
                                 trust_env=False, follow_redirects=False)

    def stream(self):
        return connect('ws://127.0.0.1:3900/ws/tts', proxy=None, open_timeout=5,
                       close_timeout=2, max_size=64000)

    async def refresh(self, client):
        response = await client.post('/setup/warmup')
        response.raise_for_status()

    async def request(self, upstream, text, voice):
        await upstream.send(json.dumps({'text': text, 'voice': voice,
                                        'language': 'Korean', 'engine': 'omnivoice'}))

    async def check_voice(self, client, voice):
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


_engine: SpeechEngine = VoiceStudioEngine()
_hai_engine: SpeechEngine | None = None
_eleven_engine: SpeechEngine | None = None


def get_speech_engine() -> SpeechEngine:
    values = {**dotenv_values(Path(__file__).resolve().parents[1] / '.env', interpolate=False), **os.environ}
    backend = (values.get('NERVIS_TTS_BACKEND') or 'voicestudio').strip()
    if backend == 'voicestudio':
        return _engine
    if backend == 'elevenlabs':
        global _eleven_engine
        if _eleven_engine is None:
            from backend.eleven_tts import ElevenLabsSpeechEngine
            _eleven_engine = ElevenLabsSpeechEngine()
        return _eleven_engine
    if backend != 'hai_gpt':
        raise SpeechError('tts_invalid_settings')
    global _hai_engine
    if _hai_engine is None:
        from backend.hai_tts import HaiGPTSpeechEngine
        _hai_engine = HaiGPTSpeechEngine()
    return _hai_engine
