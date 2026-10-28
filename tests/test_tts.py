"""Deferred synthetic tests. No voice generation, real profile/audio or external calls."""
import asyncio
import json
import unittest

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from backend.tts import SpeechRequest, check_voice, relay, router


class TTSTests(unittest.TestCase):
    def test_request_rejects_empty_long_unknown_voice_and_external_endpoint(self):
        for payload in ({'text': ' '}, {'text': '가' * 2001}, {'text': '안녕', 'voice': 'other'},
                        {'text': '안녕', 'url': 'https://example.com'}):
            with self.subTest(payload_type=tuple(payload)):
                with self.assertRaises(ValidationError):
                    SpeechRequest.model_validate(payload)

    def test_preflight_reads_only_known_local_profile_and_requires_loaded_omnivoice(self):
        async def run():
            paths = []

            def handler(request):
                paths.append(request.url.path)
                self.assertEqual(request.url.host, '127.0.0.1')
                self.assertEqual(request.method, 'GET')
                value = {'/health': {'status': 'ok', 'version': '0.5.7'},
                         '/model/status': {'loaded': True, 'checkpoint': 'k2-fsa/OmniVoice'},
                         '/profiles/f0c26d84': {'id': 'f0c26d84', 'language': 'Korean'}}[request.url.path]
                return httpx.Response(200, json=value)

            async with httpx.AsyncClient(base_url='http://127.0.0.1:3900', transport=httpx.MockTransport(handler)) as client:
                await check_voice(client, 'JARVIS')
            self.assertEqual(set(paths), {'/health', '/model/status', '/profiles/f0c26d84'})

            for model in ({'loaded': False, 'checkpoint': 'k2-fsa/OmniVoice'},
                          {'loaded': True, 'checkpoint': 'unapproved-engine'}):
                def invalid_model(request):
                    value = model if request.url.path == '/model/status' else (
                        {'status': 'ok', 'version': '0.5.7'} if request.url.path == '/health'
                        else {'id': 'f0c26d84', 'language': 'Korean'})
                    return httpx.Response(200, json=value)
                async with httpx.AsyncClient(base_url='http://127.0.0.1:3900', transport=httpx.MockTransport(invalid_model)) as client:
                    with self.assertRaises(ValueError):
                        await check_voice(client, 'JARVIS')
        asyncio.run(run())

    def test_relay_forwards_pcm_before_done_and_waits_for_playback_ack(self):
        async def run():
            generated = asyncio.Event()
            output = []

            class Browser:
                async def send_json(self, value):
                    output.append(value)
                    if value['type'] == 'done': generated.set()
                async def send_bytes(self, value): output.append(value)
                async def receive_text(self):
                    await generated.wait()
                    return json.dumps({'type': 'playback.finished'})

            class Studio:
                def __init__(self): self.request = None
                async def send(self, value): self.request = json.loads(value)
                async def __aiter__(self):
                    yield json.dumps({'type': 'start', 'sample_rate': 24000, 'channels': 1, 'format': 'pcm16'})
                    yield b'\0\0\1\0'
                    self_pcm = output[-1]
                    if self_pcm != b'\0\0\1\0': raise AssertionError('PCM was buffered until completion')
                    yield json.dumps({'type': 'done'})

            studio = Studio()
            await relay(Browser(), studio, SpeechRequest(text='한국어 응답.'))
            self.assertEqual(studio.request, {'text': '한국어 응답.', 'voice': 'f0c26d84', 'language': 'Korean', 'engine': 'omnivoice'})
            self.assertEqual(output, [{'type': 'start', 'sample_rate': 24000, 'channels': 1, 'format': 'pcm16'}, b'\0\0\1\0', {'type': 'done'}])
        asyncio.run(run())

    def test_route_rejects_cross_origin_and_invalid_input_without_studio_connection(self):
        app = FastAPI()
        app.include_router(router)
        with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)) as client:
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect('/api/tts/stream', headers={'origin': 'https://example.com'}): pass
            with client.websocket_connect('/api/tts/stream', headers={'origin': 'http://127.0.0.1:5173'}) as ws:
                ws.send_json({'text': ' ', 'voice': 'JARVIS'})
                result = ws.receive_json()
                self.assertEqual(result['type'], 'error')
                self.assertNotIn('traceback', str(result).lower())

    def test_relay_waits_for_actual_playback_and_exits_on_browser_disconnect(self):
        async def run(disconnect):
            generated, release = asyncio.Event(), asyncio.Event()

            class Browser:
                async def send_json(self, value):
                    if value['type'] == 'done': generated.set()
                async def send_bytes(self, _value): pass
                async def receive_text(self):
                    await release.wait()
                    if disconnect: raise WebSocketDisconnect()
                    return json.dumps({'type': 'playback.finished'})

            class Studio:
                async def send(self, _value): pass
                async def __aiter__(self):
                    yield json.dumps({'type': 'start', 'sample_rate': 24000, 'channels': 1, 'format': 'pcm16'})
                    yield b'\0\0'
                    yield json.dumps({'type': 'done'})

            task = asyncio.create_task(relay(Browser(), Studio(), SpeechRequest(text='응답.')))
            try:
                await asyncio.wait_for(generated.wait(), 2)
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                release.set()
                if disconnect:
                    with self.assertRaises(WebSocketDisconnect): await task
                else: await task
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        asyncio.run(run(False))
        asyncio.run(run(True))
