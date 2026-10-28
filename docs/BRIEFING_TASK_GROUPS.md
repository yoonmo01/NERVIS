# TODO groups (2026-10-24)

Daily briefing now reads all incomplete tasks, up to200, with explicit has_more_tasks. It never changes task dates/status. Priority/order: overdue, today, remaining; then deadline/time/planned date, undated last. Completed tasks excluded, each task appears once.

- overdue / 기한 지난 일: deadline date before requested day, or deadline time before now when requesting the actual current Asia/Seoul day. Date-only deadline is not overdue until next day.
- today / 오늘 할 일: not overdue and planned_on or due_on equals requested day. For other requested dates the card says 해당 날짜 할 일.
- remaining / 남은 할 일: all other unfinished tasks, including future/undated and past planned dates without an overdue deadline. A past planned date alone does not imply a missed deadline.

Server task_group goes to the card and bounded model facts. Model receives up to20 task summaries with group labels, per-group counts for the returned list, and overflow flags; it must not infer no tasks just because today is empty. Empty card groups are hidden. Synthetic preview has one item per group and never calls a provider or writes DB.

User's SW Week competition remains todo, due2026-10-29 20:00, and is classified remaining on2026-10-24. This implementation reads that record only; no personal data is seeded or modified.

Home response panel expands upward within header/composer bounds. Narrow layout separates answer (upper portion) and docked briefing (lower portion), each scrolls only when available space is exhausted. Message author/time is a separate block10px above message text.
