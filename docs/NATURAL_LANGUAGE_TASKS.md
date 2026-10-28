# Natural-language task tools — 2026-10-24

Normal session conversation now supports explicit task creation, modification, completion/reopening, listing, persisted clarification and cancellation. Existing courses/weekly meeting APIs remain separate; natural-language course writes/deletion/recurrence are not included. No new table or migration was needed.

## User flow

Disable 더미 미리보기, keep the same session, and send a normal command. Clear task commands apply directly. No default deadline time is invented. Missing requested date/name/change or multiple DB candidates returns a server-generated question without writing any item in the batch. Answers fill values/choose a numbered candidate or explicitly confirm duplicates/stale targets. Reload/switch preserves the pending draft. “취소해” clears only pending drafts; already saved tasks remain unchanged.

First batch supports1..10 actions. Model translates natural dates using current Asia/Seoul date into YYYY-MM-DD and local HH:MM. Server validates actual dates/times and required fields; ambiguous language must stay as required fields, not invented dates. NLP interpretation remains subject to user live testing.

## Tools and state

- `manage_tasks`: mode apply with actions (operation create/update/complete, title query, explicit values, clear_fields, required); mode answer with optional selection/query/values/clear_fields/confirm; mode cancel.
- `list_tasks`: read actual DB tasks filtered by optional title query/status, up to20 with has_more. Includes undated/completed tasks. Today briefing filtering remains unchanged: a future deadline without a planned date is not automatically today's work.
- Values: title, planned_on, due_on, due_time, status(todo/in_progress/done). Unspecified/null values do not erase existing values. Explicit clear_fields handles removing dates/time; clearing a deadline date also clears its time.
- No task ID is accepted from model arguments. Targets come from DB title matches or the prior server-owned task references. Multiple candidates are frozen with actual IDs/version until selected. If manually changed while waiting, explicit confirmation is required. No target found for completion offers a new completed record only after confirmation; correcting the name re-runs lookup.
- Exact same-title/date creation asks before making another copy. Duplicate identical operations within a batch are rejected. Existing candidates >10 require a narrower query. User-selected stale/deleted targets never silently switch.
- Existing `conversation_sessions.state.planner` stores normalized pending action list, index/missing field, frozen candidates/versions, confirmations and last task refs. Raw SQL, credentials, descriptions and internal versions are never sent as model facts. Current command packet gets only public pending values/candidate summary.

## Transactions and receipts

ConversationStore passes its locked session DB connection into the task service. PlannerStore._update is shared by existing PATCH and tools. All resolved batch writes, final message, cached request response and updated pending state commit together. Validation happens before mutation; execution uses a savepoint inside that same transaction. AIError rolls back before the failed user turn is recorded. Failed/interrupted request IDs never auto-replay; duplicate successful IDs return cached responses without a second write.

Write tools must be a single exclusive tool batch (one manage_tasks call; multiple items inside it). Mixing a write call with brain/weather/other tool calls is rejected before execution. No delete/SQL tools or automatic retries.

The model performs intent extraction; task-write acknowledgement/question is rendered locally from the actual DB result, not a second model-generated completion claim. Typical task writes therefore use one gateway request. Other read/analysis explanation loops remain as before. If the model returns no tool call, no task mutation occurs. Pending states are preserved through unrelated read-only questions.

Task receipts render as ordinary conversation with task status/planned/deadline fields and never enter the brain screen or calculation tabs. User history remembers both the original answer and approved task summary facts. Per-call tokens/elapsed usage remain persisted.

## Manual verification (writes REAL tasks)

Use names prefixed 검증용 to distinguish from actual coursework. Same session:

1. 검증용 공모전 제출을 10월29일까지 해야 해. -> date2026-10-29, timeunspecified.
2. 그거 마감 시간을 오후6시로 바꿔줘. -> same task,18:00.
3. 그거 완료했어. -> done/completed_at set.
4. 검증용 공모전 제출 상태를 다시 할 예정으로 바꿔줘. -> todo/completed_at cleared.
5. 검증용 할 일 목록 보여줘. -> actual saved rows.

Clarification: 검증용 날짜 미정 제출을 오후6시까지 해야 해. 마감 날짜는 아직 정하지 않았어. -> asks date, no task saved. Reply10월29일. Alternative reply취소해 -> pending abandoned, no task.

Ambiguous target: create 검증용 보고서 A and 검증용 보고서 B, then 검증용 보고서를 완료 처리해줘. -> numbered candidates. Reply2번. Reload before replying to verify persisted pending state. Listing afterward shows only selected record done. The test affects actual DB when the user sends these messages; this implementation did not seed them.

## Verification and remaining

108 backend tests passed with disposable PostgreSQL databases/mock HTTP model;36 frontend tests and TypeScript/Vite build passed. New tests observed failures before fixes: tool integration, typed date/time persistence, duplicate batch, pending candidate freeze, stale confirmation, name refinement and time clearing. Fresh read-only review verified fixes. Existing bundle warning remains.

Local server restarted with existing enabled settings; actual tasks count0 at final read-only check. Zero live model/KMA calls, no .env changes, no original edits, no commit/push. Original105 hashes matched. Browser live NLP quality/mobile/FPS are not verified by this task.

Next: user verifies model extraction, then actual classes/tasks data; TTS/STT/wake word and longer-term conversation summary remain separate.
