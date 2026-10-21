# NERVIS

제공된 뇌 데이터를 음성으로 탐색하는 인터랙티브 AI 시스템을 구현하고, 실제 상호작용을 녹화·편집한 MP4로 AI Brain Art Challenge 자유주제에 제출하는 프로젝트다. 사용자가 “NERVIS”라고 부른 뒤 영역 선택·유사도·구간 비교를 요청하면 실제 계산과 화면 변경으로 응답하는 구성을 채택한다.

현재 기획은 React·Three.js 화면 + Python 분석 서버 + BAZE/HAI GPT 도구 호출이다. 실시간 받아쓰기·Gemini TTS와 Google 생성 영상도 BAZE에서 가능한지 먼저 확인한다. Google 생성 영상은 선택적인 도입·전환 소재이며 뇌 영역·파형·수치는 실제 데이터에서 직접 그린다.

기획 문서와 환경 변수 예시를 작성했고 앱용 데이터 패키지를 생성·검증했다. 대화·화면·음성 앱, 실계정 API 연결과 본편은 아직 만들지 않았다. 전체 기준은 [프로젝트 기획](docs/PROJECT_DIRECTION.md)에 있다.

## 원본 보호

`C:\NERVIS\뇌영상 시계열 예시 데이터`는 절대 수정하지 않는 읽기 전용 입력이다. 읽기와 해시 검증만 수행하고, 모든 가공 결과는 폴더 밖에 저장한다. 전체 작업 규칙은 [AGENTS.md](AGENTS.md)에 있다.

이 규칙은 작업 지침이다. 원본 폴더의 Windows 권한·속성을 변경해서 잠근 것은 아니다. `.gitignore`는 저장소 추가 제외를 담당하며 파일 쓰기를 막지 않는다.

## GitHub에 포함할 항목

| 항목 | 방침 | 이유 |
|---|---|---|
| `AGENTS.md`, `.gitignore`, `README.md` | 포함 | 작업 규칙·저장소 안내 |
| `scripts/analyze_data.py` | 포함 | 실제 데이터는 내장하지 않은 재현 가능한 분석 코드. 로컬 데이터 별도 필요 |
| `scripts/prepare_app_data.py`, `tests/test_prepare_app_data.py`, `.env.example` | 포함 | 오프라인 가공·검증 코드, 합성 자료 테스트, 실제 키가 없는 설정 예시 |
| 현재 기획·구조·시나리오·API 가이드, `docs/past/NERVIS_PROJECT_PLAN.md` | 포함 | 개발 계획·공식 API 사용법. `past`는 구 기획임을 유지 |
| `docs/DATA_ANALYSIS_PLAN.md` | 제외 | 사용자가 데이터 관련 Markdown 전체를 커밋 대상에서 제외하도록 지정 |
| `docs/DATA_PACKAGE_IMPLEMENTATION.md`, `docs/DATA_PREPARATION.md` | 제외 | 데이터 가공 구현 계획·방법·검증 기록도 같은 제외 규칙 적용 |
| `docs/DATA_OVERVIEW.md` | 조건 확인 전 제외 | 전체 RGB 표 등 제공 자료 일부를 재현할 수 있는 내용 포함 |
| `docs/DATA_ANALYSIS_RESULTS.md` | 조건 확인 전 제외 | 영역별·구간별 상세 파생 수치 포함 |
| `docs/past/NERVIS_DATA_FEASIBILITY.md` | 조건 확인 전 제외 | 20영역의 두께·부피 값 등 제공 수치를 표로 포함. 구 문서도 공개 규칙 적용 |
| 원본 데이터 폴더 전체 | 제외 | 제공받은 자료이며 구체적 재배포 조건 미확인 |
| `tmp/` 전체 | 제외 | 초기 감사 스크립트, 원본 이미지 미리보기, 임시 JSON, 로컬 경로가 담긴 이동 기록 |
| `reports/` 전체 | 기본 제외 | 상세 수치·마스크 좌표·파형 특징·PCA scores/loadings·그림과 실행 환경 포함. 재배포 조건 미확인 |
| `data/processed/` | 생성 후에도 기본 제외 | 앱용으로 가공해도 원본에서 파생된 자료임 |
| 제공받은 공모전 PDF | 조건 확인 전 제외 | 공고를 읽는 것과 파일을 재배포하는 것은 별개 |
| `.env`, 자격 증명, 가상환경·캐시 | 제외 | 비밀정보 또는 재생성 가능한 로컬 파일 |

현재의 `tmp/data_audit/audit_data.py`는 임시 탐색용이다. 정식 분석 코드는 `scripts/analyze_data.py`다. 테스트 파일을 일괄 제외할 필요는 없다. 향후 정식 테스트는 합성·공개 허용 fixture만 사용하면 코드와 함께 관리할 수 있다.

`reports/data_analysis/pca_scores.csv`와 `pca_loadings.csv`는 전체 성분을 저장한다. 둘을 결합하면 중심화 신호를 재구성할 수 있으므로 단순한 무해한 요약표로 취급하지 않는다. 이름이 보고서·그림이어도 공개 가능 여부는 내용으로 판단한다. 작은 집계값을 담은 Markdown과 상세 재구성 가능한 산출물은 구분하지만, Markdown도 재배포 허가를 보장하는 것은 아니다.

원본·PDF·`docs/DATA_*.md`·구 데이터 검토 문서·생성 산출물을 제외하므로 해당 링크와 그림은 GitHub에서 보이지 않을 수 있다. 데이터 문서는 로컬에 유지하며, 산출물은 허가받은 데이터를 두고 해당 코드를 실행해 생성한다. 공개할 항목과 조건을 먼저 정하고 선별한다. 로컬 커밋에 넣은 파일도 나중에 푸시하면 함께 전송되므로 공개 범위가 미확인인 자료는 커밋 대상부터 제외한다.

## 진행 상태 (2026-10-21 로컬 확인)

| 단계 | 상태 |
|---|---|
| 공고·설명 PDF·원본 전체 파악 | 완료 |
| 원본 105개 파일 검사와 해시 기준 기록 | 완료. 이번 확인에서도 기준과 일치 |
| 구조·시간·관계·공간 등 12개 관점의 탐색 분석 | 완료 |
| 재현 코드와 결과 | 분석 스크립트 1개, CSV 19개, JSON 1개, 그림 5개 |
| 데이터 구성·분석 계획·결과 | 작성 완료 |
| 제출 방식 | 사용자가 공유한 교수님 후속 이메일에서 실제 시스템 녹화·편집 MP4 방식 승인 |
| 프로젝트 방향·시스템 구조·시나리오·기술 | 현재 선택한 음성 탐색 시스템 기준으로 문서화 |
| BAZE/HAI GPT·Google 영상 사용법 | 공식 설정 안내·API 명세·한림대 가이드와 Google 문서 확인 |
| 구 기획 2개 | `docs/past/`에 보관 |
| 앱용 통합 데이터 패키지·마스크 ID 변환 파일 | 생성·검증 완료. 20 ROI·200점·33 마스크·33 T1, 총 71파일 |
| 환경 변수 | `.env.example` 작성. 실제 `.env`의 BAZE_API_KEY 이름·로컬 형식·Git 제외 확인 |
| BAZE 계정 모델·도구·음성 실호출 | 미검증. 목록·잔액 조회를 포함해 사전 승인 필요 |
| 제품·음성·화면·Google 생성 소재·본편 | 미구현·미제작 |

데이터 검사·탐색 분석에 이어 앱용 패키지 준비까지 마쳤다. 다음 작업은 패키지를 읽는 로컬 분석 도구와 화면 연결이며, 자연어·음성 연결에 필요한 실제 BAZE 요청은 목적·모델/엔드포인트·최대 호출 수를 설명하고 승인받은 뒤 검증한다.

환경 변수 예시는 [.env.example](.env.example)이다. 기존 `.env`를 덮어쓰지 않고 키 값은 로컬 파일에만 둔다. 선택적인 모델 변수는 승인된 모델 선택 전까지 비워둘 수 있다. 아직 앱의 환경 변수 로더를 구현한 것은 아니다.

기본 패키지는 `data/processed/nervis_v1/`, 검사 기록은 `reports/data_preparation/validation.json`이다. 기존 패키지를 덮어쓰지 않으며, 다음 명령으로 다시 검증한다.

```powershell
& 'C:\Users\coola\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 'C:\NERVIS\scripts\prepare_app_data.py' --verify-only
```

합성 자료 테스트는 `python -m unittest discover -s tests -v`로 실행한다. 의존성은 기존 NumPy·Pillow이며 외부 통신·키·SDK가 필요 없다. 상세 가공 방법은 [로컬 데이터 처리 문서](docs/DATA_PREPARATION.md)에 기록했다.

공고상 참가 신청은 2026-10-23, 최종 제출은 2026-10-29다. 약 3분·1080p MP4는 자체 제작 목표이며 대회 지정 규격으로 단정하지 않는다. A4 2쪽 이내 AI 활용 보고서 PDF도 준비한다.

## 문서와 재현

- [데이터 구성](docs/DATA_OVERVIEW.md)
- [다면 분석 계획](docs/DATA_ANALYSIS_PLAN.md)
- [분석 결과와 해석 한계](docs/DATA_ANALYSIS_RESULTS.md)
- [현재 프로젝트 기획·범위·기술·일정](docs/PROJECT_DIRECTION.md)
- [시스템 구조·데이터 패키지·도구·세션·검증](docs/SYSTEM_ARCHITECTURE.md)
- [실제 음성 대화와 영상 제작 시나리오](docs/VIDEO_SCENARIO.md)
- [BAZE/HAI GPT API·키·Codex CLI 연결 가이드](docs/BAZE_API_GUIDE.md)
- [Google 영상 모델·생성 소재·편집 흐름](docs/GOOGLE_VIDEO_WORKFLOW.md)
- [분석 코드](scripts/analyze_data.py)
- [앱 데이터 가공·검증 코드](scripts/prepare_app_data.py)

탐색 분석은 2026-10-20 실행했고 2026-10-21에는 앱용 패키지 생성·검증을 진행했다. 분석 전체를 다시 실행하거나 기준 원본 목록을 다시 쓰지 않았다. 환경 파일의 로컬 형식 확인을 실제 키 인증·모델·음성 연결 완료와 구분한다. 현재 코딩 에이전트의 모델 제공자도 변경하지 않았다.

기획·규칙·분석 코드의 기준 커밋은 `b8512e7`이다. 이후 환경 예시·가공 코드·합성 테스트와 진행 문서를 추가·갱신했다. 이번 데이터 가공 작업에서는 추가 커밋·푸시를 수행하지 않았다. 원격의 모든 이력·릴리스·첨부까지 검사했다는 뜻은 아니다.

`.gitignore`는 이미 추적된 파일에는 적용되지 않는다. [Git 공식 문서](https://git-scm.com/docs/gitignore)의 설명처럼 추가 제외와 과거 이력 삭제를 구분한다. 규칙 파일은 [OpenAI 공식 AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)에 따른 프로젝트 지침이다.
