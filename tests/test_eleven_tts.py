"""Synthetic mock transport only. Never sends an ElevenLabs request."""
import asyncio
import json
import unittest
from unittest.mock import patch

import httpx

from backend.eleven_tts import ElevenLabsSpeechEngine, ElevenSpeechStream, speech_settings
from backend.speech_engine import SpeechError


class ElevenTTSTests(unittest.TestCase):
    def test_full_response_converted_once_to_pcm_without_discovery(self):
        async def run():
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(200, content=b'\0\0\1\0', headers={'Content-Type': 'audio/pcm'})
            engine = ElevenLabsSpeechEngine()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch('backend.eleven_tts.speech_settings', return_value=('synthetic-key', 'eleven_v3', 'syntheticVoice')):
                    self.assertEqual(await engine.check_voice(client, 'ignored'), 'syntheticVoice')
                    await engine.refresh(client)
                self.assertEqual(calls, [])
                stream = ElevenSpeechStream(client, 'synthetic-key', 'eleven_v3')
                await engine.request(stream, '합성 시험입니다.', 'syntheticVoice')
                frames = [frame async for frame in stream]
            self.assertEqual(len(calls), 1)
            request = calls[0]
            self.assertEqual(request.url.host, 'api.elevenlabs.io')
            self.assertEqual(request.url.path, '/v1/text-to-speech/syntheticVoice')
            self.assertEqual(request.url.params['output_format'], 'pcm_24000')
            self.assertEqual(request.headers['xi-api-key'], 'synthetic-key')
            self.assertEqual(json.loads(request.content), {'model_id': 'eleven_v3', 'text': '합성 시험입니다.'})
            self.assertEqual(json.loads(frames[0])['sample_rate'], 24000)
            self.assertEqual(frames[1], b'\0\0\1\0')
            self.assertEqual(json.loads(frames[-1]), {'type': 'done'})
        asyncio.run(run())

    def test_auth_failure_is_not_retried_and_mp3_is_not_treated_as_pcm(self):
        async def run():
            for response, code in [(httpx.Response(401), 'elevenlabs_http_401'),
                    (httpx.Response(200, content=b'ID3!', headers={'Content-Type': 'audio/mpeg'}), 'elevenlabs_invalid_audio'),
                    (httpx.Response(200, content=b'\0', headers={'Content-Type': 'audio/pcm'}), 'elevenlabs_invalid_audio')]:
                calls = []
                def handler(request):
                    calls.append(request)
                    return response
                async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                    stream = ElevenSpeechStream(client, 'synthetic-key', 'eleven_v3')
                    await ElevenLabsSpeechEngine().request(stream, '시험', 'syntheticVoice')
                    with self.assertRaises(SpeechError) as caught:
                        _ = [frame async for frame in stream]
                    self.assertEqual(str(caught.exception), code)
                self.assertEqual(len(calls), 1)
        asyncio.run(run())

    def test_voice_is_required_and_cannot_change_destination(self):
        with patch('backend.eleven_tts.dotenv_values', return_value={}), patch.dict('os.environ', {
                'ELEVENLABS_API_KEY': 'synthetic-key', 'ELEVENLABS_VOICE_ID': '../elsewhere'}):
            with self.assertRaises(SpeechError):
                speech_settings()
