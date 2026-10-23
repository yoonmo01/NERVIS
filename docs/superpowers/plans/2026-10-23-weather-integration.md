# Weather integration plan

**Goal:** Finish KMA weather service, briefing API integration and a small manual home weather card before natural-language planner work.
**Design:** Server-only key, fixed official HTTPS endpoints, current observation + hourly forecast, timestamped data, 10-minute success / 1-minute failure cache, no retry. Weather endpoint independent of DB/AI; briefing preserves classes/tasks when weather fails. No automatic front polling. First location catalog explicitly lists supported city representative grids, rejects other locations instead of silently showing Chuncheon.
**Scope:** No natural-language writes, TTS/STT, briefing prose or management UI yet. No paid BAZE requests. At most two actual KMA requests for final live verification, other checks mocked.

- [x] Write failing mock tests for time boundaries, key handling, cache, parsing, partial/network/auth errors, unknown location and date ranges.
- [x] Implement weather service and GET /api/weather; inject into /api/briefing and tests.
- [x] Add manual home weather card and frontend presentation tests; build.
- [x] Run backend/DB regression, review, restart and live/proxy/cache verification; document actual limits.

Results: initial full Python79, final focused weather/API10, frontend33 and build passed. Fresh review parser TypeError was reproduced and fixed. Live Chuncheon app request used2 KMA calls; proxy/weather/briefing cache reuse confirmed. No AI calls or data writes. Current app AI was observed PAUSED; its .env activation was preserved, not changed. No natural-language planner implementation in this phase.
