# Persistent conversations — 2026-10-24

The normal composer now uses a persistent PostgreSQL session. It restores the last browser-selected session after reload. A new session starts empty; old rows are retained. The history panel shows user/assistant messages and failed/in-progress markers. No paid request is made by creating, loading or switching sessions. Synthetic briefing preview never creates messages or calls the conversation DB unless the user explicitly uses the separate new-conversation control.

## Storage and API

- `conversation_sessions`: UUID primary key; state JSONB (last validated view context, last result references, last assistant message); creation/update timestamps.
- `conversation_messages`: identity sequence, session UUID, request UUID, server-owned role, original text, running/complete/failed status, metadata JSONB and timestamp. Unique(session_id,request_id,role).
- Metadata stores per-call input/output/cache/reasoning usage when available, elapsed turn seconds, approved summary facts and cached local response. Billing is retained inside the cached response only when the provider supplies it; missing billing means unknown, not zero.
- POST `/api/conversations` with `{}` creates a session. GET `/api/conversations/{uuid}` returns its text history and state, without cached raw results/internal facts.
- POST `/api/ai/chat`: optional session_id/request_id UUID pair. Both required together. Browser always supplies both. Legacy stateless requests remain supported.

The browser stores only the selected session ID in localStorage; messages live in PostgreSQL. Browser storage failure is explicitly reported. DB restore failure blocks normal sends rather than silently starting memoryless; reload-history/new-session controls recover. The history panel is available on home and analysis. Restoring context does not recreate old 3D scenes/calculation tabs or briefing animations.

## Context boundary and follow-ups

For each normal turn, server loads all completed user/assistant messages in order. User packets retain historical timestamp/context. Assistant history includes exact previous answer plus only the approved tool-summary builder output. Raw image/mask, full signals, arbitrary paths and cached raw results never enter model history. Current date/timezone are supplied again; current explicit command/view state takes precedence. The server retains previous result references rather than trusting a client-supplied conversation transcript.

Clarification replies/cancellation are interpreted against this raw history; no separate summarization model call or RAG. Current state is context/result references/last answer, NOT a validated planner pending_action. Before adding actual natural-language writes, add a typed pending action with validated task/course ID, explicit missing fields and resolved dates; do not treat conversational text as authority to write.

All history is retained. A serialized outbound history above240,000 UTF-8 bytes is explicitly rejected with `conversation_history_too_large_start_new`; no silent truncation or automatic summary. This is a temporary size guard, not a token estimate. Usage measurements will inform later summarization.

## Reliability

A PostgreSQL session advisory lock prevents concurrent turns for a session, including across server workers. The running user message commits before AI starts. Same request UUID/body reuses a cached successful response. Changed payload conflicts; failed/interrupted UUIDs cannot be replayed. A running record with no lock owner is marked interrupted on the next new request. No retries/backlog/model switch. Browser timeout may leave processing continuing; refresh history before another request. A DB failure after a paid call can leave outcome unknown; no automatic resend.

Failures preserve known usage. Partial explanation failures preserve both model-call usage entries. API usage and BAZE credit units remain distinct; no credit/balance API is called. Legacy AI-wide busy lock remains.

## Local migration

Migration003 adds two empty tables only. `compose.yaml` includes003 for NEW volumes. For EXISTING volumes: take a new pg_dump backup first, confirm neither conversation table already exists, apply003 once using psql ON_ERROR_STOP or a transaction; never reinitialize the volume or replay001. A partial schema requires investigation, not a replay. No automatic migration on backend startup.

This installation backed up the existing DB to ignored `tmp/conversation-migration/nervis-before-conversations-20261024-014910-107d10.dump` (11,122bytes, PGDMP signature checked), then applied003. Before/after courses/class_meetings/tasks counts all0. Backup restore was not tested. This is a local single-user app, without remote account authentication.

## Remaining

Natural-language planner writes, typed pending actions, real course/task registration, automatic summary, actual STT/TTS and live multi-turn response quality are not part of this step. AI activation/env files stay unchanged.

## Session picker follow-up — 2026-10-24

Header controls and status now share one flex row with align-items:center. On <=1200px the decorative center heading is hidden to leave room; narrow screens place the group below the brand.

GET `/api/conversations?limit=50&offset=0` lists bounded pages (limit1..100) ordered by last successful activity, with id/title/timestamps/message_count and has_more. The panel has a session list and message area. Selecting a session loads history/state, updates the saved browser selection only after success, and clears the previous response/analysis/briefing display. Session changes stay blocked while a turn is running. New conversation resets local selection only; the first real send creates the DB session. Every old session is preserved, and empty sessions are hidden before pagination.

Title fallback derives from the first user's first sentence/line (36 characters). From 2026-10-24, after the first successful session response commits, one background BAZE request uses only the first question/answer (up to2000 characters each) to create a Korean topic title, usually6–15 characters, maximum20. It has no tools, max_output_tokens80, and store=false. Existing session state atomically records title_attempted before the network request; failures retain the fallback and never retry. Generated title and title-call usage/time stay in session metadata, never conversation messages or model history. JSONB merges preserve concurrent planner/context updates. No schema migration and no retroactive title batch. List refresh updates the visible title. Manual rename/delete remains unimplemented.

Browser verified existing ten-message session selection and restoration after reload, with both control vertical centers matching the status center (<0.01px difference). No model request was sent by the implementation.

## Empty-session correction

The New conversation button now clears local selection/draft/view without POST /api/conversations. Session creation occurs lazily in ensure() on the first normal message send. Merely typing, opening history, reloading a fresh composer or using synthetic briefing preview does not create a session. GET list filters by EXISTS user message before ordering/LIMIT/OFFSET, so historical unused empty rows do not fill pages or has_more. Existing empty rows are not deleted; existing populated history remains accessible. A failed actual send with a persisted user message still counts as a used session.

Verified12 focused conversation tests and frontend build. Actual browser clicked New conversation three times; DB count remained10, list showed only the existing ten-message session. No model request or schema migration.

2026-10-24 task write phase: typed state.planner pending actions now connected, with shared transaction connection and AIError rollback before failed-turn recording. Task cancellation/selection/missing-field writes follow NATURAL_LANGUAGE_TASKS.md. Older pending-action-not-implemented notes are previous checkpoints.
