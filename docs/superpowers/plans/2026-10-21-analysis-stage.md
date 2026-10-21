# Common composer and analysis stage implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement the tasks in this existing workspace.

**Goal:** Share one text/voice input field and expand the local analysis preview into a data-driven spatial stage with paired region detail, sample playback and window selection.

**Architecture:** Existing FastAPI endpoints provide ranking, comparisons, windows and registered images. The frontend derives point geometry and ROI crops from local PNG pixels in memory. Actual MRI remains visible beside the spatial treatment; depth is display composition, not reconstructed anatomy. No new backend, credential, voice or cloud service.

**Tech stack:** Existing React, TypeScript, Three.js/R3F, SVG, Canvas2D and native HTML controls.

**Spec:** `docs/FRONTEND_DESIGN.md` sections 8 and 11, plus the user's explicit instruction to implement both scopes.

## Constraints and rulings

- Original data is read-only; processed files, source manifest and `.env` stay unchanged. Derived screen captures stay in ignored `reports/analysis-stage/`.
- Continue in the user's existing checkout and running local servers; an extra worktree would omit the ignored local package and separate the requested live app. Do not commit or push in this task.
- Keep paid API/STT/TTS/wake-word work deferred. Voice mode shares the editable field but clearly says it is unconnected; never simulate microphone activity.
- Start with the highest positive Pearson correlation among homologous pairs returned by the real local search. Manual selection remains available after completion.
- Use window=50 samples, step=10 samples; preserve the backend's full-record z-score scale. Playback is a display at ten samples per second, not acquisition time.

## Review focus

- Old/aborted responses cannot overwrite a newer selection; failures release the input lock.
- Mask IDs, array rows and sample numbers preserve their meaning, including absent ROIs and constant signals.
- Source image orientation is preserved; spatial depth is explicitly artistic and not physical millimetres.
- Home/hidden-tab/audio preview pauses playback and WebGL work; selections and drafts survive transitions.
- Desktop 1280x720 and native Chrome retain readable data with composer open. Keyboard, reduced motion and image/WebGL failure have usable alternatives.

## Tasks

- [x] 1. Add failing synthetic tests for slice choice, pixel geometry, ROI bounds and sample playback; implement the pure helpers and run the suite.
- [x] 2. Unify the composer field and voice-mode indicator without recording or transmission; verify draft, focus and keyboard behavior.
- [x] 3. Implement local analysis loading/locks, MRI-based spatial rendering, paired ROI crops, window selection, playback and accessible detail views. Test real local API behavior and error recovery.
- [x] 4. Run type/build and Chrome checks, inspect screenshots, perform one fresh-context review, fix important findings and update current docs and preservation evidence.

Completed 2026-10-22. HTTP/version failures use synthetic fetch tests; real local success paths use Chrome and offline Python expectations. Server interruption/WebGL fallback/OS reduced motion/recording FPS were not rerun. Chrome automation did not produce document.hidden=true, so hidden pending-load timing remains unverified at runtime; visibility guards and the important review finding were fixed and statically rechecked. Evidence: ignored reports/analysis-stage/; current scope and limitations: docs/FRONTEND_DESIGN.md section12. No paid calls, data/env changes, commit or push.
