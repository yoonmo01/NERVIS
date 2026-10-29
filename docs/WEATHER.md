# KMA weather integration (2026-10-23)

## 2026-10-29 예보 최고·최저 보완 — 수정, 미검증

최신 getVilageFcst 응답에서 요청 날짜의 TMN(최저)/TMX(최고)를 우선 읽는다. 당일 값이 누락됐고
최신 예보 조회 자체는 정상 완료됐다면 당일 02시 발표분을 최대 한 번 추가 조회해 빈 값만 채운다.
02시 발표가 아직 이용 가능한 발표가 아니면 전날 23시를 후보로 쓰며, 최신 발표와 같거나 더 늦은 후보는
조회하지 않는다. 미래 날짜는 이번 추가 조회를 하지 않는다. 실패한 최신 요청을 재시도하는 방식이 아니며,
인증 오류/연결 실패 시 추가 호출하지 않는다. 현재 관측값/시간별 예보/이미 있는 최고·최저는 덮어쓰지 않는다.

최고·최저의 basis는 forecast이며 실제 하루 관측 극값으로 표현하지 않는다. low_issued_at/high_issued_at으로
각 값이 나온 발표 시각을 함께 보관한다. 남은 시간별 TMP의 최소·최대를 하루 최고·최저로 계산하지 않는다.
보완해도 값이 없으면 null과 daily_temperature_unavailable을 유지한다. 최고·최저만 있어도 부분 결과로
사용할 수 있다. 기존 캐시를 공유하며 성공 10분·부분/실패 1분 정책은 유지한다. 비캐시 당일 조회는
최대 3회(관측 1, 최신 예보 1, 필요할 때 보완 예보 1), 미래 조회는 기존 1회다. 아래 과거 최대 2회 설명보다 우선한다.

브리핑 날씨 카드에는 예보 최저/최고를 각각 표시하고, AI 설명은 기존 daily 요약 전달 경로로 실제 값을
받는다. 로컬 기본 안내에도 조회된 예보 최고·최저만 읽도록 연결했다. 환경 파일·TTS 설정·원본 자료는 바꾸지 않았다.
합성 테스트에 누락 보완·최신 값 보존·보완 한도·캐시·시간별 기온으로 추정하지 않는 사례를 추가했으나
사용자 수동 확인 요청에 따라 실행하지 않았다. 실제 기상청/AI/TTS 호출, 테스트·빌드·서버 재시작·커밋은 하지 않았다.

사용자 확인: 백엔드 재시작 후 새 날씨/브리핑 요청을 보낸다. 날씨 카드의 예보 최저·최고와 응답 내용을 확인한다.
공급자가 값을 제공하지 않으면 여전히 정보 없음이 나올 수 있다. 더미 미리보기는 실제 조회 검증이 아니다.

Follow-up: manual home weather widget has been removed in favor of command-triggered animated cards. `/api/weather` and the KMA service remain available to AI tools. See BRIEFING_FLOW.md; the earlier manual-card notes are the previous checkpoint.

## Current behavior

- Home has a collapsible manual weather card. No request on mount, no polling. Empty location uses the server default (춘천 unless NERVIS_WEATHER_LOCATION overrides).
- GET `/api/weather?location=춘천&date=2026-10-23` works without DB or AI. Omit date for today in Asia/Seoul.
- GET `/api/briefing` preserves actual calendar/tasks and replaces the previous weather placeholder with this same service's result. Unknown locations, missing keys and weather errors do not remove calendar/tasks.
- Server-only NERVIS_KMA_API_KEY from root .env; OS environment overrides. Encoding-form keys are decoded once before HTTPX parameter encoding. Existing .env was not edited by implementation. Restart after changing credentials/default location.
- Fixed official HTTPS gateway: getUltraSrtNcst for today's observation; getVilageFcst for hourly temperature, sky and precipitation probability. No alternate host, redirect, retry, version query or LLM call.
- Up to two upstream requests per uncached today lookup, one for future dates. Success cached 10 minutes, partial/failure 1 minute, shared by weather and briefing endpoints. Concurrent lookups serialize through the same cache. Restart clears memory cache.
- Observation uses the last safely published hour (45-minute margin); forecast release uses a 20-minute margin. Timestamped in Korea time. Missing measurements remain null, not zero. Forecast low/high remain null when not supplied; remaining hourly min/max are not mislabeled as whole-day extrema.

## Location and date limits

First catalog: 춘천, 서울, 부산, 인천, 대전, 대구, 광주, 제주 representative forecast grids; city-name aliases ending 시 supported. This is not arbitrary address/geolocation resolution. Unknown names return unknown_location with supported_locations, never another city's weather. No GPS permission or precise personal location is sent. Only Chuncheon was tested live; other catalog locations are not independently live-verified.

Today through three days ahead are accepted; outside dates return date_unavailable without a provider request. Forecast availability still depends on the published data. Observations are never attached to a future date. Historical weather is not supported. Raw provider payloads, keys and request URLs are not returned to the browser or logged by this service.

Source and service terms: [기상청 단기예보 조회서비스](https://www.data.go.kr/data/15084084/openapi.do). Provider advertises free access; configured account traffic quotas still apply.

## Verification

Initial backend suite passed 79 tests including 7 mock weather checks and real PostgreSQL tests in a disposable synthetic database. Fresh review reproduced malformed category data causing TypeError; the test was observed failing and the parser now rejects non-string categories safely. Final focused weather/API suite: 10 passed, including weather failure with calendar/tasks preserved and weather availability without DB. Frontend 33 tests plus TypeScript/production build passed after timestamp display update. Existing large JS bundle warning remains.

Actual app manual Chuncheon lookup called each KMA endpoint once (2 requests total), displayed observation and hourly forecasts. Direct Vite-proxied weather and briefing then reused that cache (cached=true); unsupported location did not call KMA. Browser screenshot and HTTP evidence: `reports/weather-app-20261023-01/`. No BAZE requests, task writes, root .env modification, commit or push. No original/processed brain data changes.

## Next boundary

This does not route natural-language weather or planner requests through `/api/ai/chat` yet. That endpoint remains brain-analysis-only. Next: natural-language planner tools, relative-date resolution, ambiguous target clarification and actual DB write acknowledgements, followed by integrated briefing prose/management UI. The home weather card is a minimal manual integration, not the final briefing layout. Voice and wake word remain deferred.
