# Current cortical preview

`nervis-cortical-brain.glb` replaces the mathematical shell in the current screen. It derives the two cerebral surfaces from [Innerscene Brain](https://www.innerscene.com/tools/library/3d-parts/brain-10d8f88f), which the publisher explicitly releases as CC0 and describes as adapted from MakeHuman/MPFB CC0 assets. [Publisher terms](https://www.innerscene.com/tools/library/terms). This is provenance, not a claim that NERVIS authored the source cortex or that its anatomical accuracy was clinically verified.

The source was transformed to presentation coordinates (+X anatomical left, +Y up, -Z posterior), lightly processed, and divided into18 authored landmark/geodesic surface proxies. Two folded insular sheets were separately authored. There are22 meshes/20label IDs and no provided MRI, masks, timeseries, textures or patient coordinates. Boundaries are approximate, not an atlas match. Older `nervis-schematic-brain.glb` remains unchanged for rollback. The previous BodyParts3D candidate's license discrepancy remains unresolved and its geometry is not bundled here.

---

# NERVIS schematic brain preview

`nervis-schematic-brain.glb` is newly authored mathematical presentation geometry: two hemisphere shells and twenty individually named schematic ROI meshes. It contains no provided MRI, label images, timeseries, textures or patient coordinates. Units are presentation units, not millimetres. glTF axes are +X anatomical left, -X right, +Y superior and -Z posterior; the default posterior/superior view places anatomical left on screen left.

This is a general-location illustration, not an atlas segmentation or individual reconstruction. Broad anatomical relationships were referenced in earlier work; shape, folds, dimensions and partitions were authored for this project. BodyParts3D had been viewed earlier for orientation. Its meshes and coordinates are not imported into this asset; that reference history is retained rather than replaced by a claim that it was never consulted.

The earlier downloaded candidate's README (CC BY 4.0) and OBJ headers (CC BY-SA 2.1 Japan) still conflict. That unresolved record belongs to the earlier candidate and is preserved in the local delivery notes. New geometry is not a legal determination about the earlier candidate. Prior candidate files are not bundled here.

Blender materials, drivers, particles and compositor effects are intentionally represented by frontend shaders rather than included in the geometry GLB. The actual provided 2D MRI/masks remain available only through the existing local API.
