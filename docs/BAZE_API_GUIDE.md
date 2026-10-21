# BAZE·HAI GPT API 연결 가이드

확인: 2026-10-21. 사용자가 지정한 [Agent Setup 원문](https://docs.mindlogic.ai/agent-setup/prompt.md)과 공식 색인→에이전트 문서→OpenAPI 명세, 한림대용 `hallym-ac` 가이드를 읽고 정리했다. **실제 키 설정·모델 목록 조회·유료 호출·코딩 에이전트 설정 변경은 수행하지 않았다.**

사용자의 추가 지침에 따라 실계정 API 요청은 목록·잔액·견적 조회를 포함해 목적·모델/엔드포인트·최대 호출 수·비용 확인 여부·중단 조건을 먼저 설명하고 승인을 받은 뒤 실행한다. 아래 절차는 사용 방법이며 자동 실행 승인이 아니다. 로컬 키 형식 검사는 서버 인증 성공과 구분한다.

## 1. HAI GPT를 사용한다는 의미

HAI GPT는 기관에서 사용하는 서비스명이며 Gateway는 모델 요청을 중계하는 API다. API의 `model` 값에 서비스 이름을 임의로 넣지 않는다. 해당 키의 조직·그룹에 허용된 모델 ID를 조회해 선택한다.

공식 안내가 지정한 이 배포의 기본 주소는 `https://factchat-cloud.mindlogic.ai/v1/gateway`다. 키는 발급한 배포에 종속되며 다른 Gateway 호스트와 섞어 쓰지 않는다. Bearer 또는 `x-api-key` 인증을 지원한다. NERVIS는 서버에서 Bearer 인증을 사용한다. [인증](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/getting-started/authentication)

## 2. 앱 연결과 코딩 에이전트 연결의 차이

| 대상 | 바뀌는 것 | NERVIS와 관계 |
|---|---|---|
| NERVIS 앱 | Python 서버의 AI 요청 주소·키·모델 | 작품의 실제 명령 해석·응답 |
| 개발용 Codex CLI | 사용자의 Codex 설정과 실행 환경 | 코드를 작성하는 개발 도구의 모델 제공자 |
| 현재 실행 중인 Codex 앱 세션 | 앱·호스트가 관리하는 실행 모델 | 문서나 프로젝트 `.env` 작성만으로 전환됐다고 볼 수 없음 |

사용자가 인용한 Agent Setup은 코딩 에이전트 설정 안내다. 같은 Gateway를 NERVIS 서버에서도 SDK·HTTP로 사용할 수 있으므로 앱 연결법을 별도로 정의한다. 이번 문서 작업에서 사용자 전역 설정을 덮어쓰거나 현재 대화가 BAZE 모델에서 실행된다고 주장하지 않는다.

## 3. 키 준비·보관 원칙

1. HAI GPT의 API Gateway 메뉴에서 본인 계정으로 키를 발급한다. 메뉴·발급 권한이 없으면 기관 설정을 확인한다.
2. 키는 발급 시 한 번 표시되는 비밀값이다. 대화·문서·스크린샷·GitHub에 붙이지 않는다.
3. 앱은 서버 환경 또는 Git 제외된 로컬 `.env`에서 `BAZE_API_KEY`를 읽는다. 문서·테스트·프런트엔드에는 실제 키를 넣지 않는다.
4. 브라우저에 노출되는 `VITE_` 환경 변수에 키를 넣지 않는다. 웹소켓도 초기에는 서버가 Gateway를 중계한다.
5. 개발 도구용 연결을 실제로 진행한다면 기존 설정 보관과 환경 변수 전달 범위를 확인한 뒤 적용한다. 공식 문서의 Bash 셸 설정을 Windows에 그대로 실행하지 않는다.

아래는 **예정 환경 변수 명세**다. 지금 `.env`를 생성한 것이 아니며 빈 값은 실행 가능한 설정이 아니다.

```dotenv
BAZE_API_KEY=
NERVIS_BAZE_BASE_URL=https://factchat-cloud.mindlogic.ai/v1/gateway
NERVIS_LLM_MODEL=
NERVIS_TTS_MODEL=
NERVIS_VIDEO_MODEL=
```

비밀값은 로컬에서만 입력하고, 모델 변수는 아래 목록 조회·시험을 통과한 ID로 채운다. 별도 OpenAI 직접 API 키가 필요한 구조로 계획하지 않는다. OpenAI SDK는 BAZE의 호환 API를 호출하는 라이브러리로 사용한다.

## 4. 모델 목록을 먼저 확인

첫 인증 검증은 `GET /models/`다. 전체 URL은 `https://factchat-cloud.mindlogic.ai/v1/gateway/models/`이고 `Authorization: Bearer ...` 헤더를 서버에서 보낸다. 키를 로그로 남기지 않는다.

| 조회 | 목적 |
|---|---|
| `/models/` | 실제 계정에 노출되는 모델 ID·종류 확인 |
| `/models/?type=llm` | 대화·도구 호출 후보 |
| `/models/?type=audio` | TTS·파일 STT 등. 같은 audio라도 용도를 확인 |
| `/models/?type=video` | Google 영상 후보와 실제 사용 가능 여부 |

예정 Python SDK 사용 형태는 다음과 같다. 공식 호환 설정을 설명하는 예시이며 실행하지 않았다.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://factchat-cloud.mindlogic.ai/v1/gateway",
    api_key=os.environ["BAZE_API_KEY"],
)
model_ids = [item.id for item in client.models.list().data]
```

설정 안내의 `gpt-5.6-terra`는 초기 시험 후보이지 현재 계정의 사용 가능 모델로 확인된 값이 아니다. 실제 목록에서 GPT 후보를 고른 뒤 한국어·도구 인자·맥락·속도·비용을 짧게 시험한다. 실시간 STT의 권한은 파일 STT 활성화 여부와 실시간 문서의 조건도 확인한다. [모델 목록](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/getting-started/models), [SDK 연결](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/integrations/openai-sdk)

## 5. NERVIS 대화·도구 호출

GPT 계열은 `POST /responses/`를 우선 검증한다. 일반 채팅 모델은 `/chat/completions/`도 지원하지만, Responses 전용 모델을 Chat Completions에 넣지 않는다. 서로 다른 API의 도구 호출 이벤트 형식을 섞지 않는다. [Responses 문서](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/responses-api), [Chat Completions 문서](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/chat-completions)

예정 루프는 다음과 같다.

1. 사용자의 확정 발화, 현재 선택·구간, 도구 정의를 모델에 보낸다.
2. 모델의 도구 이름·인자를 검사하고 Python에서 실제 기능을 실행한다.
3. 결과를 로컬에 저장하고 화면 상태를 변경한다.
4. 외부 전송이 허용된 결과 요약만 모델에 반환한다. 미확인 모드에서는 결과 핸들·작업 상태만 전달하고 상세 결과는 로컬에서 표시한다.
5. 같은 도구 호출 ID에 대응하는 결과를 돌려주고 후속 응답을 받는다. 실제 수치·이름은 로컬 결과와 대조한다.

모델에 임의 코드 실행·셸·원본 경로 탐색 권한을 주지 않는다. 도구 목록은 [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)에 정의한다. SDK 기본 주소를 그대로 사용해 BAZE 키를 다른 사업자의 서버에 보내지 않도록 서버 시작 시 목적지 호스트를 검사한다.

## 6. 실시간 음성 인식

우선 경로는 Gateway가 지원하는 Soniox 실시간 받아쓰기다. 공식 주소는 `wss://factchat-cloud.mindlogic.ai/v1/gateway/soniox/transcribe-websocket`, 안내 모델은 `stt-rt-v5`다.

- 브라우저→NERVIS 서버→Gateway 순서로 중계하고 서버 연결 헤더에서 인증한다.
- 공식 예시처럼 첫 프레임에 모델·PCM 형식·샘플레이트·채널·한국어 힌트를 설정하고 이후 오디오 바이트를 보낸다. 초기 규격은 PCM16 LE, 24kHz, 모노로 맞춘다.
- 최종 토큰만 명령으로 확정한다. 종료할 때 빈 텍스트 프레임을 보내고, 빈 바이너리 프레임과 혼동하지 않는다.
- 연결·키·동시 세션·크레딧 오류를 사용자에게 상태로 표시한다. 듣기 세션의 오디오는 외부 서비스로 전송되므로 사용자가 활성화한 동안만 실행한다.

일회용 브라우저 토큰과 음성 대화용 Realtime·Gemini Live도 문서에 있지만 초기 본안은 서버 중계형 STT + GPT 도구 호출로 유지한다. 모든 음성 기능을 하나의 음성 대화 모델로 바꾸는 것은 별도 검증 대상이다. [실시간 음성](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/realtime)

대안인 파일 STT는 `POST /audio/transcriptions/`에 `multipart/form-data`로 업로드한 뒤 `GET /audio/transcriptions/{operation_id}/`에서 완료를 확인하는 비동기 방식이다. 공식 안내 모델은 `stt-async-v5`이며 현재 계정에서의 호출은 미확인이다. 대화 지연이 크면 본 촬영의 기본 입력으로 채택하지 않는다. [파일 STT](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/audio-stt)

## 7. Gemini TTS 응답 음성

`POST /audio/speech/`를 사용한다. 문서에 안내된 `gemini-3.8-flash-tts` 등을 계정 목록·짧은 한국어 시험으로 확인하고 실제 ID를 고정한다.

| 항목 | 사용할 방식 |
|---|---|
| `input` | 실제 응답 문장. 말투 지시를 섞어 읽게 하지 않음 |
| `voice` | 허용된 목소리 중 한국어·분위기를 듣고 선택 |
| `instructions` | 모델이 지원할 때 톤·속도·말투 지시 |
| 응답 형식 | 공식 문서상 PCM16 LE, 24kHz, 모노. MP3 바이트로 가정하지 않음 |

로컬에서 PCM에 WAV 헤더를 붙이거나 Web Audio로 재생하고, 편집 단계에서 필요한 샘플레이트로 변환한다. 짧은 실제 답변을 합성하며 사전 녹음 답변을 실시간 응답처럼 사용하지 않는다. 수치가 포함된 문장의 외부 전송 범위가 미확정이면 해당 부분은 로컬 TTS를 쓴다. [TTS 문서](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/audio-tts)

## 8. 같은 키로 Google 영상 생성

문서는 `google/gemini-omni-flash/v1.1`을 안내한다. 계정의 video 모델 목록에 있는지 확인한다. Gateway 경로는 Google 직접 API와 다르며, 안내상 중간 제공 경로가 있으므로 Google에 직접 연결한 것과 동일한 전송 경로로 취급하지 않는다.

1. 같은 모델·파라미터로 `POST /estimate/`에 견적을 요청한다.
2. `POST /video/generation/`에 `model`, `prompt`, 필요한 `parameters`를 보내 작업을 만든다.
3. 반환된 `operation_id`를 보관한다. 이를 임의로 분해·다시 조립하지 않는다.
4. `/video/generation/{operation_id}/`에서 상태를 확인한다. **조회·다운로드에 생성 시 모델의 `model` 쿼리가 필요하다.**
5. 완료 후 응답이 안내하는 다운로드 경로를 사용해 결과를 제작 소재로 저장하고 실제 길이·해상도·오디오를 검사한다.

요청 접수 시 과금되는 작업이므로 시간 초과를 새 생성 요청으로 처리하지 않는다. 실패 작업도 최종 상태를 확인해야 하며 자동 환불을 보장된 즉시 환불로 안내하지 않는다. 프롬프트·파라미터·작업 ID·견적·실제 크레딧을 비공개 제작 기록에 남긴다. [견적 API](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/estimate), [영상 API](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/video-generation)

구체적인 모델 구분·소재 선택·편집 흐름은 [GOOGLE_VIDEO_WORKFLOW.md](GOOGLE_VIDEO_WORKFLOW.md)를 따른다. 영상 생성은 앱의 음성 분석 루프와 분리한다.

## 9. 개발용 Codex CLI 설정 방법

이 절은 사용자가 인용한 설정 안내를 Windows 작업 맥락에서 정리한 것이다. **NERVIS 앱 설정과 별개이며, 아래 값을 실제 전역 설정에 쓰지 않았다.**

실제 연결 시에는 기존 `%USERPROFILE%\.codex\config.toml`의 모델·프로바이더·프로필을 확인·보관한 뒤 필요한 항목만 병합한다. 공식 안내의 구성 형태는 다음과 같다. 모델 값은 조회된 사용 가능 GPT ID로 조정한다.

```toml
model = "gpt-5.6-terra"
model_provider = "factchat"

[model_providers.factchat]
name = "BAZE"
base_url = "https://factchat-cloud.mindlogic.ai/v1/gateway"
env_key = "BAZE_API_KEY"
wire_api = "responses"
```

`base_url` 끝에 `/responses`를 붙이지 않는다. CLI가 경로를 덧붙인다. 키는 Codex 프로세스가 실제로 읽는 환경에 전달되어야 한다. 프로젝트 `.env`를 작성했다고 모든 CLI·데스크톱 앱이 이를 자동으로 읽는다고 가정하지 않는다.

검증 순서는 모델 목록 조회→새 CLI 프로세스의 짧은 응답→합성·비민감 파일의 도구 실행이다. 현재 실행 중인 대화를 재설정하거나 지금 세션의 제공자가 바뀌었다고 표현하지 않는다. [Codex CLI 공식 연동](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/integrations/codex-cli)

공식 선택 도구 `@mindlogic-ai/baze` CLI는 모델·크레딧·미디어·개발 에이전트 실행을 도울 수 있다. NERVIS 앱의 필수 의존성은 아니며 지금 전역 설치·로그인·추가 스킬 설치는 하지 않는다. [Baze CLI](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/integrations/baze-cli)

## 10. 실패·비용·연결 완료 판단

| 상황 | 확인·처리 |
|---|---|
| 401 | 키 누락·잘못된 키·발급 배포 불일치. 다른 호스트에 키를 시험 전송하지 않음 |
| 403 | 조직·그룹·Gateway·모델 권한 확인. 서비스 UI에서 보이는 것과 API 허용은 구분 |
| 404 | 기본 주소·엔드포인트·모델 ID·Responses 전용 여부 확인 |
| 400 | 모델의 도구·추론·샘플링·TTS·미디어 파라미터를 확인 |
| 429·일시적 5xx | 제한된 재시도와 상태 안내. 중복 유료 생성 요청 금지 |
| 크레딧 부족·필터 차단 | 응답·연결 이유를 기록하고 중단. 성공 답변으로 대체하지 않음 |

사용량은 키 소유 계정에 청구된다. 기관 UI의 무료·무제한 사용 권한이 API에 그대로 적용된다고 가정하지 않는다. Gateway 견적·크레딧과 Google 직접 API의 가격·결제는 별개다. [Gateway 과금](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/pricing)

연결 완료는 다음을 실제로 통과한 뒤에만 기록한다.

- 인증된 모델 목록과 선택한 실제 모델 ID 확인.
- 합성 자료의 도구 호출→로컬 실행→결과 회신 성공.
- 한국어 명령·맥락·잘못된 인자·오류 처리 확인.
- STT·TTS 형식·권한·응답 시간·비용 확인.
- 뇌 자료의 외부 전송 가능 범위를 정하고 제한이 적용됨을 확인.
- 키가 브라우저·로그·Git 변경 목록에 포함되지 않음을 확인.

## 참고한 공식 진입점

- [사용자 지정 Agent Setup](https://docs.mindlogic.ai/agent-setup/prompt.md)
- [문서 색인](https://docs.mindlogic.ai/llms.txt), [문서 조회 규칙](https://docs.mindlogic.ai/AGENTS.md), [OpenAPI 명세](https://docs.mindlogic.ai/openapi.json)

공식 문서의 공개 명세와 실제 기관 계정의 활성 기능이 다를 수 있다. 이 가이드는 사용법을 확인한 상태이며 실계정 호환성을 확인한 결과 보고서가 아니다.
