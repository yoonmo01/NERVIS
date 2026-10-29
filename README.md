# NERVIS

로컬 뇌 데이터의 비교·관계 검색 결과를 3D 뇌 모형, MRI 단면, 시계열로 보여주는 음성 대화 프로젝트입니다. 일정·수업·할 일 조회와 관리도 지원합니다. 로컬 STT, BAZE/HAI GPT의 AI 도구 호출, ElevenLabs 응답 TTS를 연결합니다.

## 설치와 설정

Windows 단일 PC 실행 기준입니다. Python 3.11, Node.js 22.20, Docker Desktop 환경에서 확인했습니다.

```powershell
cd C:\NERVIS
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm.cmd ci
```

최초 한 번 `.env.example`을 루트 `.env`로 복사하고 필요한 값을 입력합니다. 이미 `.env`가 있다면 덮어쓰지 마세요.

| 설정 | 용도 |
| --- | --- |
| `BAZE_API_KEY`, `NERVIS_LLM_MODEL` | AI Gateway 키와 모델 |
| `NERVIS_AI_ENABLED` | AI 활성화. 예시는 `false`, 실제 사용 시 `true` |
| `NERVIS_DB_PASSWORD`, `NERVIS_DB_PORT` | 로컬 PostgreSQL. 기본 포트 15432 |
| `NERVIS_KMA_API_KEY`, `NERVIS_WEATHER_LOCATION` | 기상청 키와 기본 지역 |
| `NERVIS_TTS_BACKEND` | `elevenlabs`, `hai_gpt`, `voicestudio` |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_MODEL_ID`, `ELEVENLABS_VOICE_ID` | ElevenLabs 키·모델·내 음성 ID |
| `NERVIS_TTS_MODEL`, `NERVIS_TTS_VOICE` | HAI GPT TTS 선택 시 모델·목소리 |
| `NERVIS_VOICESTUDIO_VOICE` | VoiceStudio TTS 선택 시 저장 프로필 |

DB와 백엔드 모두 **루트 `.env` 하나**를 사용합니다. `.env.database`는 사용하지 않습니다. 기존 DB를 계속 쓸 때는 기존 비밀번호를 유지해야 합니다. 프런트는 루트 `.env`를 읽지 않으며 키를 브라우저에 넣지 않습니다.

AI와 외부 TTS 요청은 과금될 수 있습니다. 오류가 난 요청을 자동 재전송하지 않습니다.

## 로컬 자료

- 앱용 데이터 패키지: `data/processed/nervis_v1/`. 코드 저장소에 실제 데이터는 포함하지 않습니다. 허가된 로컬 자료로 `scripts/prepare_app_data.py`를 사용해 준비합니다. 기존 패키지 검증은 `--verify-only`를 사용합니다.
- STT: 설치된 Whisper large-v3 Turbo 캐시를 재사용합니다. 한국어 받아쓰기는 `ko`, 호출어 대기는 `en`으로 인식합니다. CUDA 사용 가능 시 GPU를 사용하고 자동 모델 다운로드는 하지 않습니다. Windows GPU DLL은 기존 VoiceStudio 설치 경로를 참조합니다.
- 고정 음성: `frontend/public/audio/cues/`에 사용 권리가 있는 `Welcome_Back_Sir_V2.mp3`, `Yes_Sir_V2.mp3`, `Right_Away_Sir_V2.mp3`를 별도로 준비합니다. 현재 선택은 `features/activation/fixedCues.ts`에 있습니다.
- 뇌 모형의 출처·라이선스 기록은 `frontend/src/assets/README.md`와 `HOLOGRAM_README.md`에 유지합니다. 모형의 영역 위치는 제공 데이터의 정밀한 개인별 해부 경계를 뜻하지 않습니다.

## 실행

터미널 1:

```powershell
cd C:\NERVIS
docker compose up -d --wait
.venv\Scripts\python.exe -m backend
```

터미널 2:

```powershell
cd C:\NERVIS\frontend
npm.cmd run dev
```

브라우저에서 `http://localhost:5173/`을 엽니다. 백엔드는 `127.0.0.1:8000`에서 실행하며 프런트의 `/api` 프록시로 연결합니다.

`docker compose up`은 기존 볼륨을 재사용합니다. 매번 DB를 새로 만들지 않습니다. 앱 서버는 각 터미널의 Ctrl+C로 종료하고, DB도 중지하려면 루트에서 `docker compose stop`을 실행합니다. DB 보존을 위해 볼륨 삭제 옵션을 사용하지 마세요.

## 사용 흐름

- `NERVIS 깨우기`로 마이크 권한을 허용하고 박수 두 번으로 인트로를 시작합니다. 처음 진입은 Ctrl+Shift+Space로도 가능합니다.
- 이후 `HEY NERVIS` 또는 마이크 버튼으로 받아씁니다. 질문 중 첫 음성 이후 약 1.5초 무음이면 녹음을 끝내고 최종 인식을 기다립니다.
- 확정 문장은 기존 초안 뒤에 추가됩니다. 사용자가 수정하고 보내기를 눌러야 전송됩니다. T 버튼으로 텍스트 질문도 입력할 수 있습니다.
- 접수 안내음 후 실제 도구 결과와 AI 설명을 준비합니다. 응답 음성을 전체 생성한 다음 분석 무대와 함께 재생합니다.
- 분석 화면의 MRI·응답·계산 결과 탭, 영역 선택, 시점 버튼, 샘플 재생·이동 창 선택을 사용할 수 있습니다.
- 음성 출력은 설정한 엔진을 사용합니다. 새 대화·명시적 음성 중지 등은 기존 요청의 화면·재생 소유권을 해제합니다.

## 폴더 구성

```text
backend/
  app.py, __main__.py  서버 구성·실행
  analysis/           데이터·계산·요청 스키마
  ai/                 모델 요청·근거·설명
  planner/            수업·할 일·브리핑·일정 API
  conversations/      대화 저장
  speech/             STT·TTS·엔진 어댑터
  weather/            날씨 조회
frontend/src/
  App.tsx, main.tsx   전체 화면·요청 흐름
  features/
    activation/       인트로·박수·호출어·고정 음성
    conversation/     공통 입력·응답·대화 기록
    briefing/         날씨·수업·할 일 카드
    analysis/         3D 뇌·MRI·시계열·계산 결과
    speech/           받아쓰기·TTS·재생 제어
  components/         공통 코어·화면 모델
  styles/             공통 스타일
  assets/             뇌 모형·셰이더·매핑·출처
scripts/              데이터 가공·로컬 검증 등
database/            PostgreSQL 초기화 마이그레이션
```

## 검증

프런트 타입 검사·배포 빌드:

```powershell
cd C:\NERVIS\frontend
npm.cmd run build
```

2026-10-30 폴더 재구성 후 확인한 범위:

- 전체 백엔드 모듈 import와 서버 기동, 데이터·단면·비교·검색·이동 창·상세 분석 API 및 입력 검증.
- 프런트 빌드, 프록시·GLB·셰이더·마이크 워크릿 경로, 이동 전후 본문·계산 로직 일치.
- 기존 PostgreSQL 볼륨에서 `.env`의 비밀번호를 백엔드와 Compose가 동일하게 해석하고 연결함.
- 실제 텍스트 AI 분석 2건: 좌우 영역 비교, 가장 높은 상관관계 검색. 모두 모델 근거 기반 설명 정상 완료.
- 응답 TTS 2건과 분석 화면 전환·재생 후 입력 잠금 해제. 음질 청취 평가는 하지 않음.
- MRI 확대·영역 변경·계산 결과·시점·샘플 재생·이동 창 선택·홈 복귀. 브라우저 콘솔 오류 없음.

마이크·박수·호출어 실제 입력, 음질, 응답 음성 재생 중 화면의 동시 움직임, 모든 AI 명령·DB 쓰기·브라우저 조합을 검증한 것은 아닙니다. 자동 테스트 폴더는 사용자 요청으로 제거했습니다. 큰 프런트 번들 경고는 남아 있습니다.

## 데이터와 비밀정보

`뇌영상 시계열 예시 데이터/`는 읽기 전용 원본이며 수정·이동·재저장하지 않습니다. 실제 원본·가공 자료·상세 결과·키·고정 음성은 로컬에 보관합니다. `.env`, `tmp/`, `reports/`, `data/processed/`와 설치·빌드 산출물은 `.gitignore`로 제외합니다. 원시 MRI·마스크·전체 시계열·키는 외부 모델에 보내지 않으며, 앱이 허용한 요약 근거만 설명 요청에 사용합니다.
