# Model source and modification record

Source input: `C:/NERVIS/reports/brain-model/anatomy-surface-20261022-01/nervis-cortical-brain.blend`.

Input SHA256: `7A5FFB41A2EFFAEFBEB1C2A54C7384F0D46320F69AD556A7C5348DEEEE7B12B3`.

This task reused the locally available public cerebral meshes and provenance from the input revision. No new remote model or patient image was acquired in this task.

- Publisher listing: https://www.innerscene.com/tools/library/3d-parts/brain-10d8f88f
- Publisher terms: https://www.innerscene.com/tools/library/terms
- License identified by the publisher: CC0 — https://creativecommons.org/publicdomain/zero/1.0/
- Publisher-described upstream: MakeHuman/MPFB CC0 assets.
- Evidence retained locally: `../anatomy-surface-20261022-01/LICENSE_PROVENANCE.md` and `C:/NERVIS/tmp/brain-model/cc0-brain-innerscene-20261022/source-page.txt`.

The listing's model-specific CC0 declaration is the provenance evidence; no separate embedded upstream license statement or independently audited chain of title is claimed. This session did not re-fetch or independently verify the website. Recommended voluntary credit: “Generic brain mesh: Innerscene library / MakeHuman–MPFB, publisher-designated CC0; holographic styling and illustrative regions modified for NERVIS.”

This task authored secondary folds, microvariation attributes, holographic materials, display particles, region controls, and rounded medial proxies. It retained generic source geometry and pre-existing illustrative ROI identifiers, remapped surface patches onto the altered cortex, and softened the authored insula meshes. These are illustrative changes, not a medical atlas or a reconstruction of a person's brain.

No BodyParts3D mesh/coordinate was introduced in this revision. The older BodyParts3D archive's inconsistent README/OBJ license labels remain unresolved and were not used as the license basis of this delivery. Patient MRI, masks, time series, and source documents are not embedded in the asset.

Repository inclusion check, 2026-10-22: the publisher model page and library terms were rechecked and explicitly allow copying, modification and redistribution under CC0. This checks the publisher declaration; it is not an independent audit of upstream ownership. The two GLSL files are project-authored rendering code from this delivery, not supplied brain data.

Shape revision, 2026-10-23: reused the local 2026-10-22 hologram delivery without acquiring a new model. Narrowed and elongated the generic cortex, adjusted the inferior temporal contour, reprojected 14 surface ROIs, and rebuilt six illustrative internal cortical surfaces (medial temporal, cingulate, insular, both hemispheres). Regenerated static surface attributes and preview particles. Kept all 20 label IDs, colors and regional signal formulas. Internal surfaces are authored proxies, not atlas or patient boundaries. Source/previous-session files remain in `reports/brain-model/shape-revision-20261023-01/`; this revision did not recheck external license pages.
