"""Synthetic PCM only: no microphone, model downloads, credentials or AI calls."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.stt import LocalSTT, PCMWindow, get_stt, router


class STTTests(unittest.TestCase):
    def test_installed_model_is_loaded_offline_and_transcription_is_korean(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('model.bin', 'config.json', 'tokenizer.json', 'preprocessor_config.json', 'vocabulary.json'):
                (root / name).write_text('synthetic')
            recognizer = Mock()
            recognizer.transcribe.return_value = (iter([SimpleNamespace(text=' 오늘 수업을 알려줘.')]), None)
            with patch('faster_whisper.WhisperModel', return_value=recognizer) as factory, patch('backend.stt.gpu_runtime', return_value=False):
                service = LocalSTT(root)
                self.assertTrue(service.status()['ready'])
                self.assertEqual(service.transcribe(np.full(16000, 2000, dtype='<i2').tobytes()), '오늘 수업을 알려줘.')
                self.assertEqual(factory.call_args.kwargs['local_files_only'], True)
                self.assertEqual(factory.call_args.kwargs['device'], 'cpu')
                options = recognizer.transcribe.call_args.kwargs
                self.assertEqual(options['language'], 'ko')
                self.assertEqual(options['task'], 'transcribe')
                self.assertEqual(options['condition_on_previous_text'], False)
                self.assertTrue(options['vad_filter'])

    def test_available_gpu_uses_quantized_turbo_and_reports_actual_device(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('model.bin', 'config.json', 'tokenizer.json', 'preprocessor_config.json', 'vocabulary.json'):
                (root / name).touch()
            with patch('faster_whisper.WhisperModel') as factory, patch('backend.stt.gpu_runtime', return_value=True):
                service = LocalSTT(root)
                service.load()
                self.assertEqual(factory.call_args.kwargs['device'], 'cuda')
                self.assertEqual(factory.call_args.kwargs['compute_type'], 'int8_float16')
                self.assertEqual(service.status()['device'], 'cuda')

    def test_missing_model_never_constructs_a_recognizer(self):
        with tempfile.TemporaryDirectory() as temp, patch('faster_whisper.WhisperModel') as factory:
            service = LocalSTT(Path(temp))
            self.assertFalse(service.status()['ready'])
            with self.assertRaises(ValueError):
                service.load()
            factory.assert_not_called()

    def test_native_work_stays_busy_after_async_awaiter_is_cancelled(self):
        import asyncio
        from threading import Event
        entered, release = Event(), Event()
        service = LocalSTT(Path('unused'))

        def native_work():
            with service.lock:
                entered.set()
                release.wait(5)

        async def run():
            task = asyncio.create_task(asyncio.to_thread(native_work))
            try:
                await asyncio.to_thread(entered.wait, 2)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self.assertTrue(service.status()['busy'])
            finally:
                release.set()
            await asyncio.to_thread(lambda: service.lock.acquire())
            service.lock.release()
            self.assertFalse(service.status()['busy'])
        asyncio.run(run())

    def test_silence_gate_and_audio_bounds(self):
        window = PCMWindow()
        voice = np.full(1600, 2000, dtype='<i2').tobytes()
        quiet = bytes(3200)
        for _ in range(50): window.feed(quiet)
        self.assertLessEqual(len(window.audio), 6400)
        window.feed(voice)
        self.assertFalse(window.final)
        for _ in range(8): window.feed(quiet)
        self.assertTrue(window.final)
        self.assertGreater(len(window.take()), len(voice))
        self.assertFalse(window.voiced)
        with self.assertRaises(ValueError): window.feed(b'x')
        with self.assertRaises(ValueError): window.feed(bytes(32002))
        for _ in range(200): window.feed(voice)
        with self.assertRaises(ValueError): window.feed(voice)

    def client(self):
        app = FastAPI()
        app.include_router(router)
        service = SimpleNamespace(status=lambda: {'ready': True, 'model': 'large-v3-turbo', 'language': 'ko'},
                                  load=lambda: None, transcribe=lambda audio: '한국어 확정 문장.')
        app.dependency_overrides[get_stt] = lambda: service
        return self.enterContext(TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 50000)))

    def test_stream_eof_commits_once_and_reports_summary_without_persistent_audio(self):
        client = self.client()
        with client.websocket_connect('/api/stt/stream', headers={'origin': 'http://127.0.0.1:5173'}) as ws:
            self.assertEqual(ws.receive_json(), {'type': 'status', 'stage': 'ready', 'device': 'cpu'})
            ws.send_bytes(np.full(1600, 2000, dtype='<i2').tobytes())
            ws.send_json({'type': 'input_audio.end'})
            self.assertEqual(ws.receive_json(), {'type': 'final', 'final_kind': 'utterance', 'text': '한국어 확정 문장.'})
            summary = ws.receive_json()
            self.assertEqual(summary['final_kind'], 'summary')
            self.assertEqual(summary['segments'], [{'text': '한국어 확정 문장.'}])
            self.assertEqual(summary['language'], 'ko')

    def test_cross_origin_and_malformed_audio_are_rejected(self):
        from starlette.websockets import WebSocketDisconnect
        client = self.client()
        with self.assertRaises(WebSocketDisconnect):
            with client.websocket_connect('/api/stt/stream', headers={'origin': 'https://example.com'}): pass
        with client.websocket_connect('/api/stt/stream', headers={'origin': 'http://localhost:5173'}) as ws:
            ws.receive_json()
            ws.send_bytes(b'x')
            result = ws.receive_json()
            self.assertEqual(result['type'], 'error')
            self.assertNotIn('traceback', str(result).lower())
