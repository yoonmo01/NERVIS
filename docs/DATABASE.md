# Local PostgreSQL foundation

Approved scope: Docker PostgreSQL, default public schema, three tables. No brain files or existing analysis results are migrated. No preferences/semesters/exception/history tables. No login or remote deployment in this step.

## Start and connect

Run at the repository root:

```powershell
docker compose --env-file .env.database up -d --wait
docker compose --env-file .env.database ps
docker compose --env-file .env.database exec -T db psql -U nervis -d nervis
```

Host: 127.0.0.1; port: 15432; database/user: nervis. Password is in ignored `.env.database`; do not publish it or output resolved Compose configuration. The existing root `.env` remains unchanged. This DB account is the local initialization owner; before remote deployment provision a restricted runtime account.

`compose.yaml` pins PostgreSQL major 18; the resolved image digest can be inspected locally. The named volume survives container restarts/recreation. Do not use `down -v` or delete the volume: that deletes the DB. Docker Desktop must be running. Migrations 001 and 002 run only for an empty volume; changing those files does not migrate an existing DB. Existing installations must apply 002 once after backup; do not rerun 001 or reinitialize the volume. Future changes need new numbered migrations applied once after backup.

## Tables

- `courses`: identity ID, name, semester_name, starts_on, ends_on, created_at, updated_at. Valid date range required; semester fields are repeated per course as requested.
- `class_meetings`: identity ID, course_id, weekday (Monday 1 to Sunday 7), starts_at, ends_at, optional location. One row per weekly time slot; duplicates rejected. Course deletion removes its slots.
- `tasks`: identity ID, title, optional description/planned_on/due_on/due_time/course_id, status (todo/in_progress/done), created_at/updated_at/completed_at. A time needs a due date; done requires completed_at, other statuses require null. Deleting a course preserves its tasks and clears the link.

SQL triggers maintain updated_at. Actual instants use timestamptz; weekly times and date-only deadlines remain local calendar values. Session timezone is Asia/Seoul. Identity sequences can have gaps, including after rolled-back tests.

## Verification and backup

```powershell
Get-Content -Raw database/verify.sql | docker compose --env-file .env.database exec -T db psql -U nervis -d nervis -v ON_ERROR_STOP=1
```

Verification uses only synthetic rows and rolls them back. It never reads the brain data or calls BAZE.

For backup, use a new filename under ignored `tmp/` (example filename must not replace an existing backup):

```powershell
docker compose --env-file .env.database exec -T db pg_dump -U nervis -d nervis -Fc -f /tmp/nervis-backup.dump
docker compose --env-file .env.database cp db:/tmp/nervis-backup.dump tmp/nervis-backup.dump
```

A volume is not a backup. Copy backups to a separate safe location. Restore a dump into a **new empty test database**, not over live data, with pg_restore --exit-on-error; verify it before any replacement. Backup/restore execution is not implied by these instructions.

## Implemented API contract (2026-10-23)

Weather follow-up: `/api/weather` and `/api/briefing` now use the KMA service; previous not_connected notes below describe the earlier checkpoint. See `docs/WEATHER.md` for current limits, cache and verification. Natural-language planner tools and integrated management UI are still not connected.

- GET/POST `/api/courses`; PATCH/DELETE `/api/courses/{id}`.
- GET/POST `/api/courses/{id}/meetings`; PATCH/DELETE `/api/class-meetings/{id}`.
- GET/POST `/api/tasks`; PATCH/DELETE `/api/tasks/{id}`. PATCH handles completion/reopening and completed_at together.
- POST `/api/tasks/batch`: atomic registration of 1..50 items.
- GET `/api/db/status`: local DB connectivity/schema/timezone check, independent of model authentication.
- GET `/api/briefing?date=YYYY-MM-DD&location=서울`: actual classes and pending tasks; weather currently reports not_connected, never fabricated values. Date defaults to today in Asia/Seoul. Earlier unfinished planned tasks carry forward; future-only tasks are excluded. Undated tasks remain in the task list rather than being assigned to today automatically.

FastAPI validates typed fields and transactions and uses parameterized SQL. The shared `PlannerStore` functions are available for future model tools; no model adapter is connected yet. The model receives neither SQL execution nor DB credentials. Responses contain local record fields, not credentials/SQL/driver error details. Invalid inputs return 422, missing rows 404, conflicts 409, unavailable DB 503. DB failure does not prevent existing brain analysis endpoints from loading.

All POST creation requests require an `Idempotency-Key` UUID header. Repeating the same key with the same normalized operation/body returns the original response without another insert; changing the payload or endpoint returns 409. Technical table `api_requests` stores the payload hash and original JSON response in the same transaction as the write. Failed batch writes roll back both records and receipt. Receipts retain the original response even after an entity is edited/deleted; they are local private records and have no automatic expiry yet. A retried creation returns the original acknowledgement; use GET for current state. PATCH uses row locks and validates merged fields; completing/reopening a task sets/clears completed_at server-side. DELETE is explicit and repeat deletion returns 404.

Courses, course meetings and tasks support `limit` (1..200) and `offset`. Courses optionally filter `semester`; tasks optionally filter `status`, `planned_on`, inclusive `due_before`, `course_id`. Meetings are listed within one course. Briefings cap each list at 200 and expose has_more flags. No model calls are used for any planner endpoint.

Inspect and exercise the API locally at http://127.0.0.1:8000/docs (Swagger). For POST, generate a new UUID once per intended creation and reuse it for retries. Example body for `/api/tasks/batch`:

```json
{"items":[{"title":"논문 읽기","planned_on":"2026-10-24"},{"title":"보고서 제출","due_on":"2026-10-30","due_time":"18:00"}]}
```

Create inputs cannot set task status/completed_at; use PATCH `{"status":"done"}` after registration. Dates use YYYY-MM-DD, local times HH:MM or HH:MM:SS. Empty/null required fields and unknown fields are rejected. Optional dates/notes/course links can be explicitly cleared via PATCH. Clear due_on and due_time together when removing a timed deadline.

Runtime uses the agreed fixed timezone Asia/Seoul; the briefing default location reads NERVIS_WEATHER_LOCATION from the root .env (OS overrides) and otherwise uses 춘천. An explicit requested weather location overrides the fallback for that request. Weather lookup, task transmission to BAZE and STT are not connected in this step.

## Additional verification, API integration

Psycopg[binary] 3.3.6 was installed and pinned in requirements.txt. The initial full Python synthetic suite passed 71 tests, including six real DB API cases in a unique disposable test database. Review found missing carry-forward of unfinished planned tasks and an unbounded bigint query filter; both were reproduced as failing tests and fixed. Seven final DB API tests then passed, including unavailable DB handling, SQL-injection text treated as data, origin rejection, PATCH/DELETE CORS, batch rollback and concurrent idempotency. A misplaced test method caused a temporary NameError and was corrected before the passing run.

Before applying migration 002, the real database was dumped to ignored `tmp/planner-api-20261023-01/before-api.dump`. Migration added api_requests without changing existing business records. Real DB counts remained zero in all four tables. Backup restore has not been exercised.

Backend was restarted; local HTTP health, DB status, courses, tasks, briefing, OpenAPI and Vite proxy to DB status returned 200; foreign-origin POST returned 403. No live AI requests or user task writes were sent. Evidence: `reports/planner-api-20261023-01/http-checks.json`.

Remaining: registration/management UI, explicit natural-language tools with relative-date handling/ambiguity checks, approved personal schedule summary boundary for BAZE, weather provider, backup restore exercise and restricted runtime DB user before remote deployment. Conversation memory, accounts, Docker deployment of the app and voice remain outside this implementation.

## Actual verification, 2026-10-23

Docker Engine 29.4.1 / Compose v5.1.3 / PostgreSQL 18.6. Compose validation passed; nervis-db-1 is healthy, mapped only to 127.0.0.1:15432. Host TCP connection succeeded. SHOW timezone returned Asia/Seoul; exactly the three expected public tables exist.

`database/verify.sql` passed against the actual PostgreSQL instance: valid writes/completion, invalid weekday/time/semester/title/status/deadline/reference rejection and course deletion semantics. All its rows were rolled back. A separate synthetic task survived container force-recreation and was then deleted; final counts are zero in all three tables. The first persistence assertion had a PowerShell dollar-quoting error; rerunning the assertion through literal standard input passed. No application data was lost.

No application CRUD API or frontend/AI integration was added or claimed tested. Backup/restore instructions were written but not executed. Original/processed brain data and the existing root .env were not modified. No BAZE calls, credits, commit or push. The official PostgreSQL image was downloaded from the registry; project data was not uploaded.
