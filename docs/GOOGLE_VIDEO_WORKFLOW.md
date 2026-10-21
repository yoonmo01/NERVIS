# Google 영상 모델 활용·제작 흐름

확인: 2026-10-21. Higgsfield를 필수로 사용하지 않고 Google 계열 모델로 영상 소재를 제작하는 계획이다. **현재 계정 연결·견적 조회·영상 생성은 실행하지 않았다.** [전체 기획](PROJECT_DIRECTION.md), [BAZE 가이드](BAZE_API_GUIDE.md)

## 1. 무엇을 사용할 수 있는가

Google의 Gemini 서비스·개발자 API·Flow 같은 제작 화면과, 그 안에서 실행하는 영상 모델을 구분한다. 현재 공식 Gemini API 영상 개요는 Gemini Omni Flash를 기본 모델로 권고하고 Veo는 특정 기능·기존 파이프라인 등의 경우를 안내한다. [Google 영상 개요](https://ai.google.dev/gemini-api/docs/video)

| 경로 | 모델·방식 | 키·접근 | 이번 프로젝트의 선택 |
|---|---|---|---|
| BAZE/HAI GPT 영상 API | 문서 ID `google/gemini-omni-flash/v1.1` | BAZE 키와 계정별 video 권한 | 먼저 확인할 경로. 기존 키로 가능한 범위부터 사용 |
| Google Gemini API 직접 연결 | 공식 ID `gemini-omni-1.1-flash`, Interactions API | Google 쪽 API 접근·결제 설정 별도 | BAZE에서 불가하거나 직접 편집 기능이 필요할 때 검토 |
| Google Flow | 브라우저의 영상·이미지 제작 화면 | Google 로그인, 계정별 이용 조건 | 수동으로 소재를 만드는 대안. 현재 로그인·기능은 미확인 |
| Veo 계열의 별도 제공 경로 | 원하는 제어 기능과 실제 제공 모델을 확인 | 해당 서비스의 권한·과금 | 기본 경로로 고정하지 않고 필요할 때 재검토 |

HAI GPT를 쓰는 것과 Google 직접 API 키를 쓰는 것은 별개다. BAZE 키를 Google API 호스트에 넣지 않는다. BAZE의 Google 영상 모델 ID와 Google 직접 모델 ID도 서로 바꾸어 사용하지 않는다. [BAZE 영상 API](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/video-generation), [Google Omni](https://ai.google.dev/gemini-api/docs/omni), [Flow](https://flow.google.com/)

## 2. 이번 일정에서 주의할 모델 종료

**Veo 3.1 Preview의 안내된 Gemini API ID들과 `gemini-omni-flash-preview`는 2026-10-22 종료 예정**이라고 공식 문서에 명시되어 있다. 이번 공모전 제출은 그 이후이므로 해당 Preview를 새 제작 파이프라인의 기본값으로 쓰지 않는다.

Google 직접 연결은 현재 GA ID를 기준으로 확인하고, BAZE는 그 Gateway가 반환하는 실제 사용 가능 ID·서비스 상태를 확인한다. Veo 전체가 모든 경로에서 같은 날 종료된다는 뜻은 아니다. [Google 종료 안내](https://ai.google.dev/gemini-api/docs/video), [모델별 가격·Preview 종료](https://ai.google.dev/gemini-api/docs/pricing)

## 3. 생성 영상과 실제 시스템의 역할

| 화면 요소 | 제작 방법 | 이유 |
|---|---|---|
| ROI 형태·위치·선택·단면 | 제공 자료에서 로컬 렌더 | 데이터의 실제 영역과 대응해야 함 |
| 파형·수치·구간·상관 | Python 계산 + ECharts | 질문 조건과 결과가 일치해야 함 |
| 실제 호출·후속 대화 | 동작 중인 NERVIS를 녹화 | 실제 API와 프로그램의 상호작용을 보여줌 |
| SF 공간·입자 배경·추상 전환 | 선택 Google 생성 영상 | 짧은 분위기·장면 전환 소재로 유용 |
| 글자·로고·자막·지표 | 로컬 그래픽·편집 합성 | 가독성과 정확한 문구 유지 |

원본 뇌 PNG·CSV·Labels·PDF나 상세 파생 결과를 Google·중간 제공사에 보내지 않는다. 자체 제작한 추상 프롬프트·공개 가능한 그래픽만 입력한다. 제공 데이터를 쓰는 본체와 생성 배경을 편집에서 합성한다. 생성 모델의 영상이 개인 뇌의 정확한 재구성이나 실행 중인 앱의 출력이라고 표현하지 않는다.

## 4. BAZE를 통한 우선 작업 순서

1. `/models/?type=video`에서 Google 영상 모델의 실제 노출을 확인한다.
2. 만들 장면을 1개 고른다. 첫 시험은 짧은 도입 배경으로 제한하고 길이·16:9·해상도·오디오 요구를 정한다.
3. Gateway의 `/estimate/`에서 같은 모델·파라미터의 견적을 확인한다. 계정 예산·실패 재시도 횟수·추가 시안 수를 정한다.
4. `/video/generation/`에 작업을 제출하고 작업 ID를 보관한다. 실제 지원하는 길이·해상도는 모델 문서·계정 응답에 맞춘다.
5. 완료 또는 실패까지 상태를 추적한다. 조회·다운로드에는 생성 모델의 `model` 쿼리를 유지한다. 시간 초과 뒤 새 작업을 중복 생성하지 않는다.
6. 받은 소재의 길이·화질·프레임레이트·오디오·불필요한 글자·형태를 확인한다. 채택하지 않은 시안도 발생 비용은 기록한다.
7. 로컬 렌더 화면과 합성하고 전환·색·음량을 조정한다. 영상 모델의 오디오는 필요하면 제외해 대사·음악과 충돌하지 않게 한다.

기본 API 사용법은 [BAZE_API_GUIDE.md](BAZE_API_GUIDE.md), 비용 확인은 [공식 견적 API](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/estimate)를 따른다. 이 절은 제작 단계의 절차이며 현재 호출을 완료했다는 뜻이 아니다.

## 5. Google 직접 API·Flow를 선택할 경우

직접 API의 현행 안내는 `google-genai` 클라이언트의 `interactions.create`에 `gemini-omni-1.1-flash`와 프롬프트·영상 출력 규격을 지정하는 방식이다. Google 전용 키·지원 지역·유료 등급·사용량을 별도로 확인해야 한다. BAZE의 비동기 작업 API와 같은 요청·응답 형식이라고 가정하지 않는다. 대화식 편집은 앞선 interaction ID를 연결하는 방식이 안내되어 있다. [Google Omni 사용법](https://ai.google.dev/gemini-api/docs/omni)

Flow는 로그인한 제작 화면에서 제공되는 모델·크레딧·저장 조건을 보고 사용한다. 이번 확인에서는 공개 진입점의 로그인 화면까지만 확인했으며 현재 계정의 생성 권한·할당량·편집 기능을 시험하지 않았다. 구독 상품에 가입했다는 이유만으로 개발자 API 비용도 포함된다고 가정하지 않는다.

## 6. 첫 시험 소재와 프롬프트

처음부터 전편 생성에 들어가지 않는다. 다음 중 한 장면을 짧게 시험하고 실제 NERVIS 화면과 어울리는지 확인한다.

| 소재 | 의도 | 합성 방식 |
|---|---|---|
| 도입 배경 | 어둠 속에서 빛·입자가 모이며 시스템이 깨어나는 분위기 | 중앙 실제 단면·NERVIS 제목은 로컬 합성 |
| 관계 전환 | 두 흐름이 닮은 리듬으로 움직이다 서로 다른 흔적을 남김 | 실제 ROI 색·그래프 장면 사이의 짧은 연결 |
| 마무리 | 추상 빛이 잦아들며 관객이 발견을 되새김 | 실제 데이터 장면에서 크레딧으로 연결 |

자체 작성한 도입 소재용 예시 프롬프트:

> Create a restrained science-fiction background for a brain-data artwork. Fine teal particles emerge slowly in a dark spacious environment, with subtle depth and calm cinematic lighting. Keep the center uncluttered for a separately composited data visualization. No anatomical brain, no interface, no text, no logos. Slow camera motion, widescreen composition.

원하는 길이·비율·해상도는 프롬프트에만 의존하지 않고 해당 경로의 파라미터로 지정한다. 실제 뇌처럼 보이는 생성물을 원자료의 형태로 혼동시키지 않도록 배경 역할을 분명하게 한다. NERVIS의 글자·데이터 색·세부 UI는 후반 작업에서 일치시킨다.

## 7. 기록과 품질 확인

각 소재에 서비스 경로·실제 모델 ID·제작 시각·프롬프트·파라미터·작업 ID·견적·실제 비용·출력 파일·선택 이유를 기록한다. 기록 위치는 `reports/production/media/`이며 상세 응답·로그·미디어를 GitHub에 자동 공개하지 않는다.

검수할 항목은 프레임 사이 형태 흔들림, 카메라 움직임, 화면 합성 여백, 가독성을 방해하는 잔광, 원치 않는 글자·로고·음성, 반복 연결의 이음새, 실제 데이터 장면과의 색·리듬 연결이다. Google 문서는 생성 영상의 SynthID 표시를 안내하므로 AI 생성 소재의 출처·사용 과정을 보고서에 남긴다. [Google 생성 영상 유의사항](https://ai.google.dev/gemini-api/docs/omni)

영상 생성이 늦거나 예산·권한 문제가 있으면 해당 배경을 직접 만든 그래픽·입자 효과로 제작한다. 핵심 음성 탐색 본편의 완성을 생성 영상의 성공에 종속시키지 않는다. 상세 시나리오와 최종 제출 검수는 [VIDEO_SCENARIO.md](VIDEO_SCENARIO.md)를 따른다.
