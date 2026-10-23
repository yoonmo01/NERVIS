# Common command and animated briefing

User-approved design: remove manual weather widget; common AI input selects weather/daily briefing/brain tools. Daily briefing stays home, animating right-side weather/classes/tasks sequentially. Brain tools retain analysis navigation. Preview must explicitly label all synthetic values, never write DB or invoke paid/external APIs.

Scope: real read-only briefing/weather AI tools and UI, synthetic preview. Planner write tools, voice and wake word remain next steps; no unsupported write success claims. Schedule/weather summary fields only are sent as tool facts, never credentials, DB receipts/raw SQL, file paths or full records. No live BAZE tests in this task.

- [x] Tests: mock tool selection/results/facts and no analysis side effects; explicit preview independent of DB/AI/network; frontend domain validation and view selection.
- [x] Add read-only tool models, shared service callbacks and bounded outbound summaries.
- [x] Remove weather widget; common preview switch, result-driven navigation, animated right-side cards and narrative placement.
- [x] Verify backend, frontend and browser with synthetic preview; document behavior/limits.

Results: initial full backend84 passed; reviewed truncation bug reproduced/fixed, focused3 passed. Frontend34/build passed. Browser confirmed daily3/weather1 cards and lock release. No live paid/external requests or DB writes. Natural-language writes remain next stage, not part of this read/visual demo.
