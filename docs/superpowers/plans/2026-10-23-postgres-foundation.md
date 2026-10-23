# PostgreSQL Foundation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement inline.

**Goal:** Run a local persistent PostgreSQL database with the three approved tables.
**Architecture:** Docker Compose runs only the DB. Existing FastAPI/React and brain package remain unchanged. Default public schema; courses, class_meetings, tasks.
**Tech Stack:** PostgreSQL 18, Docker Compose, SQL.
**Spec:** User-approved three-table design in this conversation; docs/DATABASE.md.

## Constraints and scope
No original/processed brain data migration; no paid API calls; no root .env changes. DB-only credentials in ignored .env.database. Localhost binding and named volume. AI/HTTP CRUD endpoints follow separately, not implemented in this foundation.

## Steps
- [x] Add Compose, initial transactional migration and rollback-only synthetic verification.
- [x] Generate a local DB password without displaying it; validate Compose and start DB.
- [x] Verify schema, constraints, empty business tables and restart persistence.
- [x] Document startup, backup/restore, API follow-up and actual results.
