# Center-led briefing refinement

Goal: each topic is read in the center; weather moves left, classes moves right, tasks stays center. Group uses24px gaps and borderless projection styling; docking restores existing cards.

Architecture: keep BriefingCards timers/ResizeObserver/skip and shared completion lock. Add tasks phase before overview, use CSS slot offsets around center, preserve DOM order for right docking. No backend/env/DB changes.

- [x] Update timeline boundary test, observe failure.
- [x] Implement tasks focus, compact slots, projection-to-card styles; keep reduced motion/weather-only behavior.
- [x] Run frontend tests/build, inspect actual preview and record limits.

Timings: weather0–2.8s, classes2.8–5.6s, tasks5.6–8.4s, overview8.4–10.4s, docking10.4–11.4s. Voice timing remains deferred.
