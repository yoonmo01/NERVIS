# Briefing groups and conversation presentation

Approved scope: all incomplete tasks grouped overdue/today/remaining; shared server classification for model/card; message metadata spacing; taller home answer; one separate short title request after first successful turn. No live provider tests, data edits, or retroactive title batch.

1. Add boundary tests for deadline/time/date-free grouping; change planner daily read, bounded model facts and preview; render only nonempty groups.
2. Add mocked title tests and persisted once-only claim tests; store title/attempt/usage in existing session state, keep title metadata out of model history; schedule after response commit, failures retain fallback and never retry.
3. Adjust CSS for name/time gap and available-height response panel. Run backend/frontend checks and read-only actual task check; restart backend without changing env. Fresh review of change.

Classification: deadline before requested day, or earlier time on actual current Seoul day => overdue. Otherwise planned_on equals requested day or due_on equals requested day => today. All others => remaining. A past planned date alone is not overdue. Completed tasks omitted. One response max200 tasks, ordered by group then deadline/planned date; overflow explicit.

Completed: all three tasks. New grouping import test failed before implementation. Whole backend113 passed after updating the HTTP mock contract for the additional title call; frontend36 and build passed. Final classifier output refactor: planner7 + grouping2 passed. Actual personal competition record read-only classification=remaining. Fresh review found narrow-window115px limit, fixed upper-answer/lower-card bounds. Backend restarted, existing env preserved. No live AI/weather requests, personal writes, original edits, commit or push. Browser visual/live provider title quality remain user verification.
