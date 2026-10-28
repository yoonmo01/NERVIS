# Persistent raw-history conversation implementation plan

Goal: one PostgreSQL-backed conversation across requests/reload, raw history to AI, new-conversation control, usage recording. Approved in chat2026-10-24. No live model requests or planner writes.

Architecture: two public tables conversation_sessions/conversation_messages, shared DatabaseSettings and parameterized SQL. Sessions are UUIDs, message roles/ordering are server-owned. Per-session advisory lock and durable request IDs prevent overlapping/duplicate paid calls; interrupted/failed IDs are never automatically replayed. History includes user/assistant text and only allowlisted summary facts, not raw local results. Keep dates with old messages; current date remains authoritative.

Ruling: work in current checkout to preserve the existing local dataset/server workflow; no new worktree or dependencies. Raw history retained until an explicit bounded-size error (no silent truncation/summarization). DB failure must not silently discard conversation. Stateless legacy requests remain compatible. Session details are local-only; remote auth remains out of scope.

- [x] Add failing mock history and disposable PostgreSQL tests for persistence, separation, duplicate/conflict/failure, pending follow-up and no raw result leak.
- [x] Add migration003, store/API and AI history+usage integration. Preserve existing source boundary/read-only tools.
- [x] Add persistent browser session ID, restoration/history/new conversation controls and error recovery. Preview remains entirely DB-free.
- [x] Apply migration to existing local DB after new local backup; verify synthetic integration/front tests/build, review and document exact limits.

Files: database/migrations/003_conversations.sql; compose.yaml; backend/conversations.py; backend/ai.py; backend/app.py; tests/test_conversations.py; frontend/src/useConversation.ts; App.tsx/interface.css; docs/CONVERSATIONS.md.

Checks: session IDs/payload trust, simultaneous requests, restart-interrupted request, usage absent/partial/failure, DB down, storage missing, preview without DB, raw paths/timeseries excluded. No automatic retry or .env activation. No automatic commit/push.

Execution ledger: migration003 applied after fresh PGDMP backup, planner rows unchanged. Initial full run found one old date-dependent weather assertion; test clock now fixed (production weather unchanged). Fresh review found partial second-call usage omitted; reproduced in new failing test then fixed using receipt usage. Final full backend94 passed including isolated DB tests, frontend35/build passed. Browser created empty session, reloaded/restored and opened history panel. No paid calls, env edits, source edits or commit/push. Pending action remains conversational only until planner-write phase.
