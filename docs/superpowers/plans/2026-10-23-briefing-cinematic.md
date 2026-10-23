# Cinematic briefing preview

Approved: existing synthetic preview only. Weather center -> weather left and classes center -> tasks right/three columns -> hold -> dock all to right. Core dims during presentation and returns after docking. No DB/model/weather calls or voice synchronization.

- [x] Pin deterministic full/one-card timeline and reduced-motion completion with tests.
- [x] Implement staged positioning, actual-height right docking, skip control and lock until docking finishes.
- [x] Verify frontend tests/build and browser synthetic preview, record timing and limits.

Default timings: weather0–2.8s; classes2.8–5.6s; three columns5.6–8.6s; dock8.6–9.6s. Weather-only docks at2.8s and ends3.8s. Reduced motion immediately docks. Existing common input can replay the preview. Natural-language calendar writes remain next scope.
