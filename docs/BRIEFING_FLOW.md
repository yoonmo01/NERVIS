# Common command and briefing cards — 2026-10-23

## Test the screen without credits or DB changes

1. Open home at http://127.0.0.1:5173/ and check **더미 미리보기** near the top left.
2. In the normal command box enter **오늘 할 일 알려줘** (hey NERVIS prefix also works) and send.
3. Weather appears in the center (0–2.8s), moves left as classes appear in the center (2.8–5.6s), then classes move right and tasks appear in the center (5.6–8.4s). The compact three-column layout holds (8.4–10.4s), then all cards dock on the right (10.4–11.4s). The core stays bright during presentation; soft dark gradients behind the text preserve readability. Input unlocks only after docking. 오른쪽에 정리 skips to the one-second docking transition. Reduced motion docks immediately.
4. **오늘 날씨 알려줘** shows only the weather card, docking at2.8s and finishing at3.8s. Repeat the same request to replay the effect.

All preview values including18℃ weather, three classes and three tasks are synthetic. Banner explicitly says so. GET /api/briefing/preview builds a response in memory only; no key, DB, weather call, model or paid request. Preview supports only these deterministic briefing/weather examples; it is not an AI intent test. Analysis requests require leaving preview mode and the ordinary explicitly enabled AI flow. Preview state is tab memory only.

## Real command flow

The existing POST /api/ai/chat advertises two additional read-only tools: get_daily_briefing and get_weather. Command packet includes Korean local date/timezone and existing brain focus. Instructions require actual tool selection: a current brain focus must not turn a planner request into analysis. Model routing remains the first call and grounded explanation the second; no extra classifier request.

- Daily briefing calls actual DB daily filtering plus shared KMA service. DB errors return calendar_status=unavailable (not a false empty schedule), weather still shown. Empty vs unavailable is distinguished.
- Weather alone calls the shared cached weather service, no DB required.
- Brain results retain sample/version validation and previous viewSelection logic. Frontend accepts briefing/weather as a distinct kind without requiring a brain dataset_version. A calculation result navigates to analysis; briefing/weather stays or returns home. Mixed explicit analysis+briefing prefers the analysis screen; cards remain subordinate to that view.
- Only completed tool results create cards; no permanently displayed empty cards or manual weather query form. Weather/class/task lists reflect returned data. Future date headings do not claim today.
- Narration remains visible separately from cards; there is no TTS or wake word. Card application completes before accepting another request. No backlog or interrupt queue.

Outbound facts explicitly select course name/time/location, task title/status/planned/due dates, bounded weather summary. Never send full DB records, description, receipt payloads, credentials, SQL or paths. Up to12 classes/20 tasks/8 forecast rows reach the explanation; own truncation flags and count lower-bound marker prevent claiming complete lists. Local UI keeps all returned rows, capped at200 by DB API. Normal read requests can transmit these schedule summaries to the configured BAZE service; preview never does.

## Current limits

Natural-language writes (create/complete/edit tasks), persistent conversation memory, full management UI, STT/TTS/wake word are not implemented here. The prompt explicitly forbids pretending writes succeeded. These are separate next steps after the visual review. KMA currently supports the catalog in WEATHER.md. The existing .env AI flag was preserved; preview works when the real AI is PAUSED. No automatic credential/budget activation.

## Actual verification

Initial complete backend suite84 passed (includes real isolated PostgreSQL tests and mock AI/KMA). Fresh review found summary truncation flags, reproduced and fixed, and future-date headings were corrected. Final focused briefing tests3 passed; frontend34 tests and TypeScript/build passed. Existing large JS bundle warning remains.

Actual browser: preview switch enabled, common input sent daily briefing and weather examples. Three-card and one-card layouts stayed home, applying state locked input and completed state unlocked it. No live BAZE/KMA requests or DB writes were made by this task. Rendering is inspected at the current desktop viewport; FPS, other browsers/mobile and actual model selection quality are not newly verified.

## Cinematic preview follow-up

Frontend35 tests and TypeScript/Vite build passed. Actual desktop browser verified sequential presentation, three columns, right docking without overlaps, input unlock after docking, skip control and no document overflow. Card heights are measured for docking. Long lists can still scroll when content exceeds the viewport. Records: reports/briefing-cinematic-20261023-01/. Mobile, FPS and actual voice synchronization remain unverified. This follow-up made no external API requests or DB writes; environment files and source data were untouched.

## Center-led refinement

Each topic now appears in the center before moving aside: weather left, classes right, tasks center. Projection style has soft dark background gradients without visible borders, luminous accent lines, full-opacity text and larger headings/body/temperature; existing card surfaces return during docking. Desktop column gap is24px at full width. Small screens show the active topic rather than overlapping three columns. Fresh review found visually hidden mobile summaries still accessible; visibility:hidden now also removes them from accessibility traversal.

Frontend35 tests/build passed. Browser observed classes/tasks/overview/docked and measured x224.32(weather),548.21(tasks),872.33(classes), widths300px; transparent backgrounds and borders in overview. Docked cards restored backgrounds, stacked with12px gaps and input unlocked. Evidence: reports/briefing-center-led-20261023-01/. No external requests, DB writes, env or original data changes. Actual mobile/voice/FPS not checked.
