"""Korean dictation using an already-installed model; PCM lives only in memory."""
import asyncio
from functools import lru_cache
from importlib.util import find_spec
import json
import os
from pathlib import Path
import re
from threading import Lock
from time import monotonic

import numpy as np
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from backend.planner_api import LOCAL_ORIGINS


RATE = 16000
MODEL = 'deepdml/faster-whisper-large-v3-turbo-ct2'
FILES = ('model.bin', 'config.json', 'tokenizer.json', 'preprocessor_config.json', 'vocabulary.json')
router = APIRouter(prefix='/api/stt', tags=['local Korean dictation'])
session_lock = asyncio.Lock()
dll_directory = None


def gpu_runtime():
    """Reuse installed VoiceStudio CUDA DLLs in this process only."""
    global dll_directory
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() == 0 or 'int8_float16' not in ctranslate2.get_supported_compute_types('cuda'):
            return False
        if os.name == 'nt':
            folder = Path.home() / 'AppData/Roaming/VoiceStudio/runtime/project/.venv/Lib/site-packages/torch/lib'
            if not all((folder / name).is_file() for name in ('cublas64_12.dll', 'cudnn64_9.dll', 'cudart64_12.dll')):
                return False
            if dll_directory is None:
                dll_directory = os.add_dll_directory(str(folder))
                os.environ['PATH'] = str(folder) + os.pathsep + os.environ.get('PATH', '')
        return True
    except (ImportError, RuntimeError, OSError):
        return False


def installed_model():
    cache = Path.home() / 'AppData/Local/OmniVoice/hf_cache/models--deepdml--faster-whisper-large-v3-turbo-ct2'
    try:
        revision = (cache / 'refs/main').read_text().strip()
        if re.fullmatch('[a-f0-9]{40}', revision):
            snapshot = (cache / 'snapshots' / revision).resolve()
            if snapshot.is_relative_to(cache.resolve()):
                return snapshot
    except OSError:
        pass
    return cache / 'missing'


class LocalSTT:
    def __init__(self, model_path=None):
        self.path = Path(model_path) if model_path is not None else installed_model()
        self.model = None
        self.lock = Lock()
        self.device = 'not_loaded'
        self.compute_type = None

    def status(self):
        return {'ready': find_spec('faster_whisper') is not None and all((self.path / name).is_file() for name in FILES),
                'model': MODEL, 'language': 'ko', 'device': self.device, 'compute_type': self.compute_type,
                'busy': session_lock.locked() or self.lock.locked()}

    def load(self):
        with self.lock:
            if self.model is None:
                if not self.status()['ready']:
                    raise ValueError('local_model_missing')
                from faster_whisper import WhisperModel
                device, compute = ('cuda', 'int8_float16') if gpu_runtime() else ('cpu', 'int8')
                self.model = WhisperModel(str(self.path), device=device, compute_type=compute, cpu_threads=4,
                                          local_files_only=True)
                self.device, self.compute_type = device, compute

    def transcribe(self, pcm, language='ko'):
        self.load()
        with self.lock:
            audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768
            segments, _ = self.model.transcribe(audio, language=language, task='transcribe', beam_size=1,
                temperature=0, condition_on_previous_text=False, vad_filter=True,
                vad_parameters={'min_silence_duration_ms': 500})
            return ' '.join(segment.text.strip() for segment in segments).strip()


@lru_cache(maxsize=1)
def get_stt():
    return LocalSTT()


class PCMWindow:
    def __init__(self):
        self.audio = bytearray()
        self.voiced = False
        self.silence = 0
        self.total = 0

    def feed(self, pcm):
        if not pcm or len(pcm) % 2 or len(pcm) > 32000:
            raise ValueError('invalid_pcm')
        self.total += len(pcm)
        if self.total > 120 * RATE * 2 or len(self.audio) + len(pcm) > 20 * RATE * 2:
            raise ValueError('audio_limit')
        audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768
        speech = float(np.sqrt(np.mean(audio ** 2))) >= .005
        self.voiced |= speech
        self.silence = 0 if speech else self.silence + len(pcm)
        self.audio.extend(pcm)
        if not self.voiced and len(self.audio) > 6400:
            del self.audio[:-6400]

    @property
    def final(self):
        return self.voiced and (self.silence >= int(.8 * RATE * 2) or len(self.audio) >= 15 * RATE * 2)

    def take(self):
        result = bytes(self.audio) if self.voiced else b''
        self.audio.clear(); self.voiced = False; self.silence = 0
        return result


@router.get('/status')
def status(service: LocalSTT = Depends(get_stt)):
    return service.status()


@router.websocket('/stream')
async def stream(ws: WebSocket, service: LocalSTT = Depends(get_stt)):
    if ws.headers.get('origin') not in LOCAL_ORIGINS or ws.client is None or ws.client.host not in ('127.0.0.1', '::1'):
        await ws.close(code=1008)
        return
    language = ws.query_params.get('language', 'ko')
    if language not in ('ko', 'en'):
        await ws.close(code=1008)
        return
    await ws.accept()
    from backend.tts import wait_for_standby
    try:
        await wait_for_standby(ws)
    except WebSocketDisconnect:
        return
    if session_lock.locked() or service.status().get('busy', False):
        await ws.send_json({'type': 'error', 'message': '다른 받아쓰기가 실행 중입니다.'})
        await ws.close()
        return
    async with session_lock:
        tasks = []
        try:
            await asyncio.wait_for(asyncio.to_thread(service.load), 60)
            await ws.send_json({'type': 'status', 'stage': 'ready', 'device': service.status().get('device', 'cpu')})
            window = PCMWindow()
            changed = asyncio.Event()
            ended = False
            committed = []

            async def receive():
                nonlocal ended
                while True:
                    message = await asyncio.wait_for(ws.receive(), 130)
                    if message['type'] == 'websocket.disconnect':
                        raise WebSocketDisconnect()
                    if message.get('bytes') is not None:
                        window.feed(message['bytes'])
                    elif message.get('text') and json.loads(message['text']) == {'type': 'input_audio.end'}:
                        ended = True; changed.set(); return
                    else:
                        raise ValueError('invalid_control')
                    changed.set()

            async def recognize():
                last_partial = ''
                last_decode = 0
                while not ended or window.audio:
                    await changed.wait()
                    changed.clear()
                    final = ended or window.final
                    if not window.voiced or (not final and (len(window.audio) < RATE * 2 or monotonic() - last_decode < 1)):
                        if ended: window.take()
                        continue
                    pcm = window.take() if final else bytes(window.audio)
                    text = await asyncio.to_thread(service.transcribe, pcm, language)
                    last_decode = monotonic()
                    if final:
                        if text:
                            committed.append(text)
                            await ws.send_json({'type': 'final', 'final_kind': 'utterance', 'text': text})
                        else:
                            await ws.send_json({'type': 'partial', 'text': ''})
                        last_partial = ''
                    elif text and text != last_partial:
                        last_partial = text
                        await ws.send_json({'type': 'partial', 'text': text})
                    if ended: changed.set()
                await ws.send_json({'type': 'final', 'final_kind': 'summary', 'text': ' '.join(committed),
                                    'segments': [{'text': text} for text in committed], 'language': language})

            tasks = [asyncio.create_task(receive()), asyncio.create_task(recognize())]
            await asyncio.gather(*tasks)
        except WebSocketDisconnect:
            return
        except Exception:
            try:
                await ws.send_json({'type': 'error', 'message': '로컬 한국어 인식을 완료하지 못했습니다. 모델·오디오 길이·서버 상태를 확인해 주세요.'})
            except (RuntimeError, WebSocketDisconnect):
                pass
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await ws.close()
            except (RuntimeError, WebSocketDisconnect):
                pass
