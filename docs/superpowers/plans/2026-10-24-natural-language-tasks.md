# Natural-language task writes and clarification state

Approved: task registration/update/completion + same-session missing-field/choice/cancel flow; user performs live verification. No agent live API calls, real coursework seeding, course writes, delete tools, automatic retries, new tables or .env edits.

Architecture: manage_tasks (apply/answer/cancel) and list_tasks tools. Model extracts intent/ISO dates using current Korean date; typed server validates. Server resolves targets from actual DB candidates or stored last-task refs, never accepts invented IDs. Store normalized pending action list, candidate IDs/version, missing field and validated values in existing session state. Exact duplicate creation asks confirmation. Multiple operations apply atomically after all targets/required fields resolve. Direct simple writes need no extra confirmation. Existing task API validation/update code reused in same session transaction. Task write acknowledgement is generated from actual local receipts; no extra model explanation request.

- [x] Failing isolated-DB and mock-gateway tests: create/update/complete, batch, ambiguity/select, date missing, cancel, duplicate, stale candidate, rollback/idempotency, session isolation and summary boundary.
- [x] Task schemas/manager, shared transactional update, session connection/state integration and safe grounded receipts.
- [x] Prompt/tools and frontend reply routing/status/receipt rendering; no analysis screen for task writes.
- [x] Focused+full tests/build, fresh review, restart existing enabled server, local health/UI-only checks, docs and manual test prompts.

Pending question is server-owned, persists across reload/switch; read-only interjections preserve it. First stage handles tasks only; course/meeting management stays existing manual API. Failure rolls back mutations before recording failed user turn. Cached request replays never write twice. If model returns no tool call, no DB mutation. Dates supplied as YYYY-MM-DD; optional unspecified deadline time stays absent. Natural language interpretation quality requires user live tests; no claim of full language coverage.

Ledger:108 backend/36 frontend tests and build passed. Fresh review defects reproduced then fixed (stale confirmation, refine fallback target, create clear handling). Additional candidate-freeze and duplicate-batch regressions fixed. Server PID8876 healthok/AI enabled, actual tasks count0. No paid requests/production planner writes/env edits/commit/push. Live NLP quality left for user verification.
