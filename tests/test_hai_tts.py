"""Mock-only adapter contracts; not executed during the requested edit-only pass."""
import asyncio
import json
import unittest
from unittest.mock import patch

import httpx

from backend.hai_tts import HaiGPTSpeechEngine, HaiSpeechStream
from backend.speech_engine import SpeechError


class HaiTTSTests(unittest.TestCase):
    def test_one_full_text_request_and_pcm_contract(self):
        async def run():
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(200, content=b'\0\0\1\0', headers={'Content-Type': 'audio/pcm'})
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                stream = HaiSpeechStream(client, 'synthetic-key', 'gemini-3.1-flash-tts-preview')
                await HaiGPTSpeechEngine().request(stream, '합성 시험. 전체 문장입니다.', 'Umbriel')
                frames = [frame async for frame in stream]
            self.assertEqual(len(calls), 1)
            self.assertEqual(str(calls[0].url), 'https://factchat-cloud.mindlogic.ai/v1/gateway/audio/speech/')
            self.assertEqual(json.loads(calls[0].content), {'model': 'gemini-3.1-flash-tts-preview',
                             'input': '합성 시험. 전체 문장입니다.', 'voice': 'Umbriel'})
            self.assertEqual(json.loads(frames[0])['sample_rate'], 24000)
            self.assertEqual(frames[1], b'\0\0\1\0')
            self.assertEqual(json.loads(frames[-1]), {'type': 'done'})
        asyncio.run(run())

    def test_auth_failure_is_not_retried_and_warmup_has_no_request(self):
        async def run():
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(403)
            engine = HaiGPTSpeechEngine()
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                with patch('backend.hai_tts.speech_settings', return_value=('synthetic-key', 'synthetic-model', 'Umbriel')):
                    self.assertEqual(await engine.check_voice(client, 'ignored'), 'Umbriel')
                    await engine.refresh(client)
                self.assertEqual(calls, [])
                stream = HaiSpeechStream(client, 'synthetic-key', 'synthetic-model')
                await engine.request(stream, '합성 문장.', 'Umbriel')
                with self.assertRaises(SpeechError) as caught:
                    _ = [frame async for frame in stream]
                self.assertEqual(str(caught.exception), 'tts_http_403')
                self.assertEqual(len(calls), 1)
        asyncio.run(run())
