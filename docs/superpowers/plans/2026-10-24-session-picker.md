# Conversation picker and aligned header

Approved user scope: session list/reopen, first-message title, align controls vertically with NERVIS status. No paid calls or planner writes.

- [x] Pin title derivation/stability and paginated session-list HTTP contract with failing tests.
- [x] Derive stable title from first user message (no extra AI call/schema change); add bounded list endpoint.
- [x] Put controls/status in shared flex header row, add session browser and restore/switch with old-view reset; preserve stored old sessions.
- [x] Verify focused synthetic DB tests, frontend build/tests, actual header centers and existing history selection; fresh read-only review.

Title: first sentence/line, whitespace collapsed, at most36 characters plus ellipsis. Empty session is 새 대화. Existing conversations receive the same derivation on read, no rewrite. Paginated list50 rows, no raw metadata/results. Session selection persists localStorage only after successful fetch. Switching disabled during a turn. Existing raw-history/usage contracts remain unchanged. No commit/push requested.

Fresh read-only review: no blockers; mid-width decorative heading collision avoided by hiding it <=1200px. Actual browser selected existing ten-message session, verified reload restores it, and measured header center difference <0.01px. Frontend35 tests/build and focused backend11 passed; full regression recorded separately. No paid calls, data/env edits or commit/push.
