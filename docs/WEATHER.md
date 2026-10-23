# KMA weather integration (2026-10-23)

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
