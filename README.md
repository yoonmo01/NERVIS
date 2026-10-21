# NERVIS

제공된 뇌 데이터를 음성으로 탐색하는 인터랙티브 AI 시스템을 구현하고, 실제 상호작용을 녹화·편집한 MP4로 AI Brain Art Challenge 자유주제에 제출하는 프로젝트다. 사용자가 “NERVIS”라고 부른 뒤 영역 선택·유사도·구간 비교를 요청하면 실제 계산과 화면 변경으로 응답하는 구성을 채택한다.

현재 기획은 React·Three.js 화면 + Python 분석 서버 + BAZE/HAI GPT 도구 호출이다. 실시간 받아쓰기·Gemini TTS와 Google 생성 영상도 BAZE에서 가능한지 먼저 확인한다. Google 생성 영상은 선택적인 도입·전환 소재이며 뇌 영역·파형·수치는 실제 데이터에서 직접 그린다.

기획·데이터 패키지·Python 분석 함수·FastAPI에 이어 첫 React 화면을 구현했다. 중앙 타이틀 이동, 개선한 푸른 다층 코어, 공통 입력창과 실제 MRI·마스크·좌우 파형 탐색을 실행할 수 있다. 자연어 대화·음성 인식·응답 합성과 본편은 아직 없다. 전체 기준은 [프로젝트 기획](docs/PROJECT_DIRECTION.md)에 있다.

## 원본 보호

`C:\NERVIS\뇌영상 시계열 예시 데이터`는 절대 수정하지 않는 읽기 전용 입력이다. 읽기와 해시 검증만 수행하고, 모든 가공 결과는 폴더 밖에 저장한다. 전체 작업 규칙은 [AGENTS.md](AGENTS.md)에 있다.

이 규칙은 작업 지침이다. 원본 폴더의 Windows 권한·속성을 변경해서 잠근 것은 아니다. `.gitignore`는 저장소 추가 제외를 담당하며 파일 쓰기를 막지 않는다.

## GitHub에 포함할 항목

| 항목 | 방침 | 이유 |
|---|---|---|
| `AGENTS.md`, `.gitignore`, `README.md` | 포함 | 작업 규칙·저장소 안내 |
| `scripts/analyze_data.py` | 포함 | 실제 데이터는 내장하지 않은 재현 가능한 분석 코드. 로컬 데이터 별도 필요 |
| `scripts/prepare_app_data.py`, `tests/test_prepare_app_data.py`, `.env.example` | 포함 | 오프라인 가공·검증 코드, 합성 자료 테스트, 실제 키가 없는 설정 예시 |
| `backend/`, `scripts/verify_local_analysis.py`, 로컬 분석·검증 테스트 | 포함 | 실제 데이터·키를 내장하지 않은 계산 코드와 합성 자료 검사 |
| `requirements.txt`, `tests/test_api.py` | 포함 | 현재 로컬 API·테스트 의존성 버전과 합성 HTTP 검사 |
| `frontend/` 소스·설정·package-lock·합성 테스트 | 포함 | 실제 데이터·키 없이 UI와 의존성을 재현. node_modules·dist는 제외 |
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
| 로컬 분석 함수 | 구현·실제 자료 대조 완료. 영역·신호 조회, 두 영역 비교, 조건별 검색, 이동 창, 단면 조회 |
| FastAPI 데이터·분석 서버 | 구현·로컬 HTTP 검증 완료. 시작 시 로딩, 분석 호출, 등록 단면 조회 |
| 첫 프런트 화면 | 구현. 타이틀 이동·실제 영역·단면·좌우 비교·파형 |
| 코어 개선·공통 화면 | 구현. 곡면 패널·발광 핵·빠른 회전·합성음 반응, 커진 분석 코어, 홈 입력창·분석 T/마이크. 피드백에 따라 초기 정보 카드는 제거했으며 실제 AI/마이크·날씨·개인 목록은 미연결 |
| 대화 세션·AI 도구 호출 연결 | 미구현. 자연어·후속 질문·상태 처리는 후속 단계 |
| 환경 변수 | `.env.example` 작성. 실제 `.env`의 BAZE_API_KEY 이름·로컬 형식·Git 제외 확인 |
| BAZE 계정 모델·도구·음성 실호출 | 미검증. 목록·잔액 조회를 포함해 사전 승인 필요 |
| 고급 시각화·자연어·음성·Google 생성 소재·본편 | 미구현·미제작. 첫 화면을 전체 제품 완성으로 취급하지 않음 |

직접 조작하는 첫 화면까지 연결했다. 다음은 실제 화면의 시각 방향을 검토하고, 필요한 탐색 조작을 확장한 뒤 텍스트 AI 도구 호출·대화 맥락·음성을 연결하는 단계다. 자연어·음성 연결에 필요한 실제 BAZE 요청은 목적·모델/엔드포인트·최대 호출 수를 설명하고 승인받은 뒤 검증한다.

환경 변수 예시는 [.env.example](.env.example)이다. 기존 `.env`를 덮어쓰지 않고 키 값은 로컬 파일에만 둔다. 선택적인 모델 변수는 승인된 모델 선택 전까지 비워둘 수 있다. 아직 앱의 환경 변수 로더를 구현한 것은 아니다.

기본 패키지는 `data/processed/nervis_v1/`, 검사 기록은 `reports/data_preparation/validation.json`이다. 기존 패키지를 덮어쓰지 않으며, 다음 명령으로 다시 검증한다.

```powershell
& 'C:\Users\coola\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 'C:\NERVIS\scripts\prepare_app_data.py' --verify-only
```

합성 자료 테스트는 `python -m unittest discover -s tests -v`로 실행한다. Python 3.11과 기존 NumPy·SciPy·Pillow를 사용하며 외부 통신·키·SDK가 필요 없다. Windows 링크 검사는 symlink 또는 junction 생성이 허용된 환경이 필요하다. 상세 가공 방법은 [로컬 데이터 처리 문서](docs/DATA_PREPARATION.md)에 기록했다.

## 로컬 분석 함수 사용

프로젝트 루트에서 다음 Python 코드를 실행한다. 패키지를 한 번 읽은 뒤 같은 Dataset으로 조건을 바꿔 호출한다. 시간점은 1~200 양끝 포함이고 초 단위가 아니다.

```python
from pathlib import Path
from backend.data import load_dataset
from backend.analysis import find_similar_pairs, compare_regions

data = load_dataset(Path("data/processed/nervis_v1"))
ranking = find_similar_pairs(data, scope="homologous", limit=3)
comparison = compare_regions(data, 1, 11, start=1, end=50)
print(ranking["status"], comparison["status"])
```

`backend/analysis.py`는 `get_dataset_summary`, `get_region_info`, `get_timeseries`, `compare_regions`, `find_similar_pairs`, `analyze_pair_over_windows`, `get_region_slices`를 제공한다. 결과는 데이터 버전·요청 조건·상태·주의점과 함께 JSON으로 직렬화할 수 있다. 잘못된 인자는 ValueError, 상수 신호의 상관은 `unavailable`과 `None`으로 구분한다. 반환 객체 수정은 원자료에 반영되지 않는다.

`scripts/verify_local_analysis.py`는 원본·패키지 보존을 검사하고 기존 CSV와 Pearson·Spearman 각각 190쌍, 이동 창 8,740개를 절대 오차 `1e-12`로 대조했다. 결과는 `reports/local_analysis/validation.json`에 있다. 최초 실행 명령은 `python -X utf8 scripts/verify_local_analysis.py`이며 기존 보고서가 있으면 덮어쓰지 않고 중단한다. 추가 수치 대조만 수행하려면 `scripts.verify_local_analysis.verify_reports(data, Path("reports/data_analysis"))`를 호출한다. 기존 보고서와 원본 기준을 다시 만들지 않는다.

## FastAPI 로컬 서버

현재 설치된 Python 3.11 환경에서는 프로젝트 루트에서 다음 명령으로 실행한다. 터미널에서 실행했다면 Ctrl+C로 종료한다. 서버를 이미 실행 중이면 같은 포트에서 중복 실행하지 않는다.

```powershell
Set-Location C:\NERVIS
& 'C:\Users\coola\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 -m backend
```

서버 상태는 `http://127.0.0.1:8000/api/health`, API 명세·직접 요청 화면은 `http://127.0.0.1:8000/docs`다. Swagger 화면은 기본 CDN 리소스를 사용하므로 완전한 오프라인 브라우저 환경에서는 `/openapi.json`과 직접 HTTP 요청을 사용한다. 서버 계산에는 인터넷·키·`.env`가 필요 없다.

| 요청 | 역할 | 주요 반환값 |
|---|---|---|
| `GET /api/health` | 준비 상태 | status, dataset_version |
| `GET /api/dataset` | 자료 요약 | 영역·시점·단면 수, 신호 종류, 단위, 정규화와 공간 설명 |
| `GET /api/regions` | 전체 영역 목록 | dataset_version, 20개 영역의 메타데이터 목록 |
| `GET /api/regions/{region_id}` | 한 영역 상세 | region: ID·이름·좌우·RGB·두께·부피·반대쪽 대응 ID |
| `GET /api/regions/{region_id}/slices?orientation=Axial` | 영역별 단면·추천 단면 | slices, recommended_slice, 픽셀 좌표계 설명. 각 단면에 이미지 경로·노출·경계 정보 |
| `POST /api/analysis/timeseries` | 선택 영역·구간 파형 | samples, region_ids, bold, zscore. 배열 축 sample×region |
| `POST /api/analysis/compare` | 두 영역 비교 | 두 파형·영역 메타데이터, correlation, 두께·부피의 A/B 값과 B-A 차이·단위 |
| `POST /api/analysis/pairs` | 전체/좌우 쌍 순위 | pairs의 영역 ID·상관, 후보/유효 쌍 수, 계산 불가 쌍 목록 |
| `POST /api/analysis/windows` | 이동 구간 상관 | 창별 시작·끝·상관·상태, 유효 창 수와 최소·최대 상관 |
| `GET /api/slices/{orientation}/{slice_index}/{kind}` | 등록 단면 조회 | JSON이 아닌 PNG 바이트. kind는 `t1` 또는 `mask` |

7개 분석·조회 함수의 응답에는 공통으로 `dataset_version`(데이터 버전), `analysis`(실행 함수), `parameters`(사용한 조건), `status`, `warnings`가 있다. health·영역 목록·이미지 응답은 위 표의 별도 형식이다. 마스크 PNG의 픽셀은 RGB 색이 아닌 영역 ID 0~20이고 0은 미라벨이다. 화면에서 regions의 팔레트를 입혀 표시한다.

시계열은 `region_ids`, `start`, `end`, 비교는 `region_a`, `region_b`, `start`, `end`, `method`를 받는다. 검색은 같은 구간·방법에 `scope`, `order`, `limit`를 받으며 창 분석은 두 영역·구간·방법에 `window`, `step`을 받는다. 기본 구간은1~200, 방법은pearson, 검색 범위는all, 정렬은descending, limit는5, 창은50점·10점 이동이다. z-score는 전체200점 기준 값을 잘라서 반환하며 구간마다 다시 정규화하지 않는다.

예를 들어 `/api/analysis/compare`에 아래 JSON을 POST한다. 응답은 데이터 버전·분석 조건·파형·상관·정적 지표를 포함한다. 시간점은 초가 아니며 양끝 포함이다.

```json
{"region_a": 1, "region_b": 11, "start": 1, "end": 50, "method": "pearson"}
```

JSON의 정수 필드에 bool·문자열·실수를 넣거나, 추가 필드·잘못된 구간·중복 영역을 보내면 HTTP422로 거절한다. 상수 구간은 HTTP200에 `status: unavailable`, `correlation: null`을 반환한다. 없는 단면은404, 서버 시작 뒤 이미지 변경·경로 이탈은409다. 서버는 원본 폴더·manifest·임의 파일을 제공하지 않는다.

`requirements.txt`는 로컬 서버·합성 테스트용으로 검증한 버전이다. 이번에는 이미 설치된 환경을 사용했고 패키지를 추가 설치하지 않았다. 기존 탐색 분석 스크립트의 pandas·Matplotlib와 향후 영상 도구는 이 서버용 목록에 포함하지 않았다. API 검사만 실행하려면 `python -X utf8 -m unittest discover -s tests -p test_api.py -v`, 전체 회귀 검사는 `python -X utf8 -m unittest discover -s tests -v`다. Windows 샌드박스에서 asyncio의 내부 localhost 통신이 막히면 로컬 통신과 junction 생성이 허용된 환경에서 실행한다.

실제 서버의 HTTP·PNG·입력 오류·CORS/Host 확인 기록은 `reports/backend/http_validation.json`이다. 세션·명령 해석·AI 도구 호출·이벤트·음성·DB는 아직 없다.

공고상 참가 신청은 2026-10-23, 최종 제출은 2026-10-29다. 약 3분·1080p MP4는 자체 제작 목표이며 대회 지정 규격으로 단정하지 않는다. A4 2쪽 이내 AI 활용 보고서 PDF도 준비한다.

## 첫 프런트 화면 실행

백엔드가 `127.0.0.1:8000`에서 실행 중인 상태에서 별도 터미널을 연다. Node.js 22.20 이상을 기준으로 확인했다. 처음 설치할 때만 아래 `npm ci`를 실행한다. 공개 npm 패키지만 다운로드하며 BAZE 키가 필요 없다.

```powershell
Set-Location C:\NERVIS\frontend
npm.cmd ci --ignore-scripts --no-audit --no-fund --cache ..\tmp\npm-cache
npm.cmd run dev
```

접속 주소는 `http://127.0.0.1:5173/`다. 실행 중인 서버가 있으면 중복 실행하지 않는다. 하단의 **분석 화면 미리보기**로 기존 실제 자료 화면을 열고, 현재 영역·단면을 먼저 표시하며 왼쪽의 **직접 변경**을 펼쳐 영역과 Axial/Coronal을 바꿀 수 있다. 같은 이름의 반대쪽 ROI, 전체 구간 Pearson 상관, 공통 세로축의 두 z-score 파형을 표시한다. 좌우 패널은 하단까지 늘리고 파형은 중앙 MRI와 같은 폭으로 둔다. 화면 높이에 맞춰 구체·MRI·파형과 간격을 조정하고, 매우 낮거나 좁은 창에서만 전체 스크롤을 허용한다. 홈 왕복 시 선택을 유지한다.

**코어 음량 반응 미리보기**는 Web Audio에서 만든 약 3.65초 합성음의 실제 음량을 측정한다. AI 음성·마이크·음성 인식이 아니다. 서버 연결·이미지·분석 실패는 오류로 표시하며, 로딩 중 이전 결과를 새 선택의 결과처럼 남기지 않는다. 상단은 `NERVIS 대기 · AI 연결 전`으로 표시하고 합성음 재생 중에는 `오디오 미리보기 · AI 연결 전`으로 바뀐다. 실제 AI 준비·분석 상태는 아직 없다.

| 위치·기술 | 역할 |
|---|---|
| `src/App.tsx` · React | 타이틀 순서, 홈/분석 전환, 데이터 연결 상태 |
| `src/CoreScene.tsx` · Three.js + React Three Fiber | 자체 생성한 입자·분절 구면·내부 궤도선과 프레임별 움직임 |
| `src/AnalysisView.tsx` · React + SVG | 실제 두 파형·창별 상관·선택 구간·재생·상세 창 |
| `src/BrainStage.tsx` · Three.js/R3F + Canvas2D | 실제 단면 점군·표시용 깊이/관계선·ROI 확대·MRI 병치 |
| `src/stageData.ts`, `src/analysisModel.ts` | 로컬 검색/비교/창 조회·단면 선택·픽셀 기하·샘플 범위 |
| `src/audio.ts` · Web Audio | 로컬 합성음 생성·음량 측정·중지와 자원 해제 |
| `src/api.ts` · fetch | `/api`의 로컬 서버 요청과 취소·HTTP 오류 처리 |
| `src/model.ts`, `src/model.test.ts` · Node 내장 테스트 | 타이밍·기하·마스크·파형·음량의 합성 입력 검사 |

Vite는 loopback 주소에 바인딩하고 `/api`만 FastAPI로 프록시한다. 루트 `.env`를 읽지 않으며 API 키를 브라우저로 넘기지 않는다. Vite 파일 접근 허용 범위는 `frontend/`뿐이다. 원본·패키지를 정적 공개 폴더에 복사하지 않았다. `dist/`만 별도로 열면 데이터 API가 연결되는 배포 방식까지 구현한 것은 아니다.

추가된 공통 화면은 `src/Interface.tsx`·`src/interface.css`다. 홈에서는 입력창을 펼치고 분석에서는 T·마이크 아이콘으로 접는다. 작성한 초안은 화면/모드 전환에 유지되지만 파일에 저장하거나 전송하지 않는다. AI 전송 버튼은 비활성이고 마이크 버튼은 같은 편집 가능한 입력칸을 음성 모드로 전환하며 STT 연결 전·마이크 꺼짐을 표시한다. 날씨·수업·할 일 카드는 초기 화면에 표시하지 않는다. 실제 요청→중앙 브리핑→오른쪽 위 카드 이동은 후속 구현이다. 입력칸은 예시 문구 없이 시작하며 큰 외곽 박스 대신 입력칸과 버튼만 둥근 테두리를 쓴다. 합성음 재생 중에는 새 입력과 분석 조작을 막고 종료 시 복구한다. 전체 AI 요청의 순차 처리·실제 브리핑은 후속 단계다.

프런트 검사는 `npm.cmd test`, 타입 검사와 프로덕션 빌드는 `npm.cmd run build`다. 로컬 UI 확인은 1280×720 가로 구도와 좁은 앱 패널에서 수행했다. 시작/건너뛰기·영역/방향 변경·홈 왕복·키보드 선택·로컬 음향·서버 실패/재시도를 확인했다. 원본·패키지·환경 파일 보존과 Vite 접근 차단 기록, 실제 스크린샷은 Git 제외 대상인 `reports/frontend/`에 둔다. 첫 버전의 독립 검토는 도구 할당량 제한으로 미완료였으나, 이번 코어·공통 화면 변경은 독립 정적 검토를 수행하고 발견한 초점 이동 문제를 브라우저 재현 후 수정했다. 추가 검사9개와 브라우저 기록은 `reports/frontend-v2/`에 있다. 이 버전은1280×720와 실제 앱 창에서 확인했고 모바일 등 다른 크기는 추가 확인이 필요하다. 1080p 녹화 성능·다른 브라우저/모바일·OS 움직임 축소 설정의 실제 적용은 아직 검증하지 않았다. Three.js를 포함한 큰 번들 경고와 R3F 내부 THREE.Clock 사용 중단 예정 경고는 남아 있다.

높이 대응과0.32초 입력창 전환·직접 변경 메뉴·`1~200` 표기, 실제 크롬 검증은 `reports/frontend-responsive/`에 기록한다. 마이크를 세션 단위로 켜고 요청 처리·응답 종료 후 다시 듣는 동작은 향후 음성 단계의 설계이며 아직 연결하지 않았다.

첫 피드백 반영 기록은 `reports/frontend-feedback/`다. 홈 소개·데이터 개수와 분석 상단 제목을 제거하고 코어 상태 문구를 아래로 옮겼다.

이번에는 프런트만 검사했고 기존 Python 전체 회귀 테스트를 다시 실행하지 않았다. 서버 복구 후 실제 HTTP·UI 요청은 확인했다. BAZE·LLM·STT·TTS 요청은 없고 커밋·푸시도 실행하지 않았다.

## 문서와 재현

최신 프런트(2026-10-22)는 **공통 입력창·로컬 분석 무대**까지 구현했다. 명시된 분석 미리보기를 열면 대응 쌍의 실제 상관 검색→단면 자동 선택→MRI 기반 점군·양쪽 ROI 확대·관계선→두 파형·50점 창/10점 간격 상관·선택 구간 재생으로 전개한다. 깊이·관계선은 표시용이며 정밀 3D 복원이나 직접 신경 연결이 아니다. 텍스트/음성 모드는 같은 입력칸을 사용하지만 실제 STT·AI·음성 전송은 아직 없다. 사용법·검증·남은 순서는 [프런트 설계12절](docs/FRONTEND_DESIGN.md#12-공통-입력창분석-무대-확장-2026-10-22), 실제 화면·검증 기록은 로컬 `reports/analysis-stage/`에 있다. 검사13개·타입/빌드·크롬 배치와 실제 로컬 수치 대조를 통과했으며 이번 추가 설치·유료 호출·커밋/푸시는 없다.

- [데이터 구성](docs/DATA_OVERVIEW.md)
- [다면 분석 계획](docs/DATA_ANALYSIS_PLAN.md)
- [분석 결과와 해석 한계](docs/DATA_ANALYSIS_RESULTS.md)
- [현재 프로젝트 기획·범위·기술·일정](docs/PROJECT_DIRECTION.md)
- [시스템 구조·데이터 패키지·도구·세션·검증](docs/SYSTEM_ARCHITECTURE.md)
- [프런트 시각 방향·첫 구현 범위](docs/FRONTEND_DESIGN.md)
- [실제 음성 대화와 영상 제작 시나리오](docs/VIDEO_SCENARIO.md)
- [BAZE/HAI GPT API·키·Codex CLI 연결 가이드](docs/BAZE_API_GUIDE.md)
- [Google 영상 모델·생성 소재·편집 흐름](docs/GOOGLE_VIDEO_WORKFLOW.md)
- [분석 코드](scripts/analyze_data.py)
- [앱 데이터 가공·검증 코드](scripts/prepare_app_data.py)
- [로컬 분석 함수](backend/analysis.py)
- [실제 자료 대조 코드](scripts/verify_local_analysis.py)
- [FastAPI 서버](backend/app.py)
- [HTTP 요청 모델](backend/schemas.py)

탐색 분석은 2026-10-20 실행했고 2026-10-21에는 앱용 패키지 생성·검증, 로컬 분석 함수·FastAPI와 첫 프런트 화면을 구현했다. 분석 전체를 다시 실행하거나 기준 원본 목록을 다시 쓰지 않았다. 환경 파일의 로컬 형식 확인을 실제 키 인증·모델·음성 연결 완료와 구분한다. 현재 코딩 에이전트의 모델 제공자도 변경하지 않았다.

기획·규칙·탐색 분석 코드의 기준 커밋은 `b8512e7`, 환경 예시·가공 코드·합성 테스트는 `822f352`다. 로컬 분석 함수·검증·시나리오는 `fa2c659`로 커밋했다. 그 뒤 추가한 FastAPI 서버·요청 모델·HTTP 테스트·실행 문서도 버전 관리 대상이다. 데이터·키·상세 검증 기록은 제외한다. 푸시는 수행하지 않았고 원격의 모든 이력·릴리스·첨부까지 검사했다는 뜻은 아니다.

`.gitignore`는 이미 추적된 파일에는 적용되지 않는다. [Git 공식 문서](https://git-scm.com/docs/gitignore)의 설명처럼 추가 제외와 과거 이력 삭제를 구분한다. 규칙 파일은 [OpenAI 공식 AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)에 따른 프로젝트 지침이다.
