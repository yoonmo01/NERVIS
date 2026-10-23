# Planner API Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** Connect validated course/meeting/task CRUD and local daily briefing reads to PostgreSQL.
**Architecture:** FastAPI router -> shared PlannerStore methods -> parameterized Psycopg transactions. Lazy DB connections keep brain analysis usable when Docker is off. No model/voice/UI integration or paid calls.
**Tech Stack:** Existing FastAPI/Pydantic, PostgreSQL 18, psycopg[binary] 3.3.6.
**Spec:** Approved three-table design and docs/DATABASE.md API contract.

## Constraints / rulings
- Preserve all original/processed brain files and existing .env.
- Default Asia/Seoul and weather location Chuncheon; explicit request location overrides only that request.
- Ruling: add internal api_requests table for transactional idempotency, not another business concept. Reusing a UUID with a changed operation/body returns 409. Failed batches leave no writes or receipt.
- No automatic destructive migration/reset; apply numbered migration 002 once with ON_ERROR_STOP.
- DB errors must not disclose passwords, SQL or task contents. Foreign browser origins must not mutate data. Lists are bounded and paginated.
- No task/calendar data goes to an external model in this scope; AI adapters can later call the same store functions.

## Tasks
- [x] Write real PostgreSQL isolated-database tests for CRUD, batch atomicity/idempotency/concurrency, dates, completion/reopen, origin/CORS, errors, daily filtering.
- [x] Observe failing tests, install pinned driver, implement schemas/store/router and migration.
- [x] Run actual DB integration and existing API regression tests; fix failures and review changed callers.
- [x] Apply non-destructive migration to local DB, restart backend and verify local HTTP without paid calls; record results and remaining integration work.

## Results
Initial 71-test full suite passed. Final seven DB API tests passed after review fixes (unfinished planned tasks carry forward, bigint input capped); preceding new regression failures were observed. One test placement NameError was corrected. Main DB was backed up, migration002 applied, all four tables remain empty; final backend/proxy HTTP and OpenAPI 0.2.0 verified after restart. No paid AI calls or original/root .env edits. All entity lists are paginated; final DB suite includes meeting pagination checks.
