# 로컬 한국어 마이크 받아쓰기

후속 TTS 코드 연결(시험 보류)은 [로컬 TTS와 스트리밍 조사](LOCAL_TTS.md)를 따른다.
STT의 모델·한국어 고정·부분 인식 간격은 변경하지 않았다.

2026-10-28. main의 b16c9bd에서 연결했다. 실제 헤드셋 공동 시험 후 **Whisper large-v3 Turbo / 한국어(ko) 고정 / GPU int8_float16**을 사용자가 선택했다.

## 사용

기존처럼 `python -m backend`, `frontend/`에서 `npm.cmd run dev`로 실행한다. 공통 입력창의 음성 모드 → **마이크 켜기** → 브라우저 권한 허용 → 말하기 → **마이크 끄기** 순서다. 음성 모드 진입만으로 녹음을 시작하지 않는다. 녹음 중 실제 실행 장치(GPU/CPU)를 표시한다.

- `인식 중 · 미확정`은 입력창 안에 별도로 표시한다. 약0.8초 무음 또는 발화15초에서 확정한다.
- 확정 문장만 최신 편집 초안 뒤에 추가한다. 사용자의 수정 내용을 요약으로 덮어쓰거나 중복 추가하지 않는다.
- 600자 초과 결과는 별도 편집/복사 칸에 보관한다. 공간을 만든 뒤 초안에 추가한다.
- 녹음/모델 준비/확정 대기/초과 문장 보관 중 보내기와 새 대화를 막는다. 사용자가 기존 보내기/Enter로만 전송한다.
- 마이크 끄기는 캡처를 즉시 해제하고 마지막 문장 확정을 기다린다.
- 닫기·텍스트 모드·화면 전환·탭 숨김·페이지 종료는 녹음을 취소한다. 취소 시 미확정 문장은 폐기하고 확정된 초안은 유지한다. 자동 재시작은 없다.
- 녹음은 최대2분이다. 권한 거절·장치 종료·서버 오류·시간 초과를 표시한다.

## 로컬 처리와 설치 조건

`backend/stt.py`가 브라우저의 16kHz mono signed PCM을 메모리에서 처리한다. `GET /api/stt/status`, `WS /api/stt/stream`을 기존 Vite `/api` 프록시로 연결한다. WebSocket은 지정된 localhost Origin과 루프백 연결만 허용하며 PCM 크기·누적 길이를 제한한다.

원음·전사 문장은 NERVIS STT에서 파일/로그로 저장하지 않는다. 사용자가 보내기를 누르면 기존 대화 저장/AI 규칙이 적용된다. 원본 뇌 데이터와 STT 경로는 연결하지 않는다.

VoiceStudio의 기존 설치 캐시를 읽는다:

`%USERPROFILE%/AppData/Local/OmniVoice/hf_cache/models--deepdml--faster-whisper-large-v3-turbo-ct2/`

`refs/main` snapshot에 model.bin, config.json, tokenizer.json, preprocessor_config.json, vocabulary.json이 있어야 한다. `local_files_only=True`, `language='ko'`, `task='transcribe'`, VAD를 사용한다. 모델 자동 다운로드·클라우드 대체·후처리 LLM 호출은 없다.

CUDA가 가능하면 int8_float16을 사용한다. Windows에서는 기존 VoiceStudio의 `runtime/project/.venv/Lib/site-packages/torch/lib` DLL을 읽고 **현재 NERVIS 프로세스의** DLL 검색 경로만 추가한다. 시스템/사용자 환경 설정과 환경 파일은 변경하지 않는다. CUDA 장치/필수 DLL이 없으면 CPU int8로 실행하고 표시한다. 실행 중 GPU 메모리 오류는 명시 오류로 종료하며 숨은 장치 전환·자동 재시도는 없다.

모델은 서버에서 한 번 로딩해 재사용한다. 마이크 종료 후에도 모델 메모리는 유지한다. 이미 진행 중인 원시 전사 계산은 종료 신호만으로 강제 중단되지 않을 수 있어, 실제 완료 전 busy를 유지하고 새 녹음을 막는다. 오디오 버퍼는 세션 종료 후 해제한다.

## VoiceStudio 상태와 선택 이력

시작 시 로컬 API의 0.5.7 / health ok를 다시 확인했다. 일반 ASR은 whisperx / Systran/faster-whisper-large-v3(미설치), 실제 받아쓰기 설정/로드 모델은 sherpa-whisper-tiny(CPU)였다. Turbo는 설치돼 있었지만 선택된 VoiceStudio 받아쓰기 모델은 아니었다.

1. Tiny 스트림에서 실제 마이크→입력창 도달과 초안 추가를 확인했지만, 사용자 시험에 다른 언어처럼 보이는 오인식이 섞였다.
2. 해당 VoiceStudio 스트림은 한국어 고정을 지원하지 않아, 사용자 승인으로 NERVIS가 설치된 Turbo를 직접 읽도록 변경했다. 한국어 품질은 개선됐으나 CPU 지연이 컸다.
3. 기존 CUDA DLL 재사용으로 GPU 실행을 확인했다. 사용자가 실제 헤드셋에서 속도 개선을 확인하고 이 경로를 선택했다.

새 모델 다운로드는 없었다. 더 큰 large-v3는 향후 정확도 비교 후보지만 현재는 사용자가 선택한 Turbo를 유지한다. Turbo는 large-v3의 속도 개선형이다. [Whisper 공식 비교](https://github.com/openai/whisper#available-models-and-languages), [faster-whisper GPU 안내](https://github.com/SYSTRAN/faster-whisper#gpu)

최종 STT는 VoiceStudio API를 사용하지 않아 앱이 꺼져 있어도 설치 파일이 있으면 동작한다. VoiceStudio 설정과 JARVIS/JARVIS_2 프로필은 변경하거나 사용하지 않았다.

## 코드와 검증

- `backend/stt.py`, `tests/test_stt.py`: 모델 선택·한국어 고정·PCM 제한·WebSocket·busy 회귀.
- `frontend/src/stt.ts`, `frontend/tests/stt.test.ts`: 스트림 수명·확정 중복 방지·초안 추가·권한/연결/시간 초과.
- `microphone-worklet.js`, `useDictation.ts`: 실제 PCM 캡처와 React/페이지 수명 정리.
- `Interface.tsx`, `App.tsx`, `interface.css`: 켜기/끄기·중간/확정 표시·수동 전송 잠금.
- `requirements.txt`, `frontend/vite.config.ts`: 이미 설치된 실행 라이브러리 버전과 WebSocket 프록시.

프런트 합성 검사46개, 백엔드 전체128개(34개는 명시적 DB 통합 opt-in이 없어 건너뜀), TypeScript/빌드가 통과했다. 독립 검토에서 네이티브 계산 잔류 중 busy 표시 문제를 발견해 실패→통과 회귀 검사로 수정했다. 로컬 기록은 `reports/stt-20261028/`에 둔다. 합성 입력 검사와 실제 사용자 헤드셋 확인을 구분한다.

STT 구현 단계에는 AI 자동 전송·호출어·TTS를 포함하지 않았다. 후속 TTS 코드와 미검증 범위는 이 문서 상단 링크를 따른다. 시험 서버는 프로세스에서만 NERVIS_AI_ENABLED=false / NERVIS_AI_MAX_REQUESTS=0이다. 실제 BAZE 전송·유료 API·환경 파일 변경·원본 변경은 수행하지 않았다. 대규모 한국어 정확도·장시간/다중 브라우저·녹화 FPS는 검증하지 않았다.

2026-10-28 후속 정리: 사용자 요청으로 프런트 테스트 7개를 `frontend/tests/`로 이동했다. 실행 명령과 타입 검사에 해당 폴더를 포함하고 코드·일반 GLB·마이크 worklet 참조 경로를 맞췄다. 테스트/원본 데이터를 복사하거나 새 fixture를 만들지 않았다. STT 구현과 테스트 정리를 함께 로컬 커밋하며 푸시는 하지 않는다.
