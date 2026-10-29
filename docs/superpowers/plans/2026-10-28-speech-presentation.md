# Speech presentation implementation plan

**Goal:** Dynamically associate grounded response segments with visible results and actual audio playback; strengthen the existing audio-reactive core.
**Architecture:** The existing explanation request returns optional text/target segments. Both boundaries validate targets derived from current results. One local TTS connection generates segments sequentially while the browser schedules PCM and emits cues from its audio clock.
**Constraints:** No commits, actual AI tests, environment edits, dependencies, source-data writes or external data uploads. Preserve ordinary answers when segment metadata is invalid.

- [x] Add synthetic tests for target validation, answer preservation, segment ordering, delayed playback and cancellation.
- [x] Extend the existing AI explanation, local speech relay and player with bounded segments; keep legacy plain speech working.
- [x] Drive briefing focus and task highlights from playback cues; dock safely after completion, stop or error. Remove fixed briefing timers for synchronized playback.
- [x] Increase bounded core movement using the existing real audio level, with reduced-motion support.
- [x] Run backend/frontend checks, document the contract and manual verification steps. No live AI or audio generation.

Review focus: malformed metadata, stale events after stop, audio failure before first PCM, changing sample rates, unavailable/duplicate targets, long responses, reduced motion, and retaining all results when narration omits a card.
