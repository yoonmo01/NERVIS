# Current hologram preview

The current viewer uses `nervis-hologram-brain.glb` from the local delivery `reports/brain-model/hologram-delivery-20261022-01/`. The earlier cortical and schematic models remain unchanged for rollback.

This generic illustration contains two cortex shells and twenty authored ROI proxies, not subject-specific anatomy or atlas boundaries. Source provenance and publisher-designated CC0 conditions are recorded in `HOLOGRAM_LICENSES.md`. No supplied MRI, mask or time series is embedded. The publisher's declaration is the evidence, not an independently audited chain of title.

`hologram-region-map.json` provides label IDs and exact node names. `hologram-render-contract.json` and the GLSL files preserve the delivered rendering reference. The viewer applies all four custom scalar vertex attributes, independent per-ROI strength uniforms, depth-tested translucent surfaces, deterministic surface points and a modest bloom pass. Point opacity and size are reduced for the smaller web viewport. Blender/Cycles and WebGL appearances are not claimed to be pixel-identical.

The orthographic default camera is front/superior without lateral tilt, using the delivered vertical span. Preset transitions follow the shortest positional arc independently of screen roll. Drag, wheel, arrow keys, +/- and reset remain available. Selected ROI brightness follows the existing absolute z-score display magnitude; selection remains visible at zero. This is not evidence of increased neural activation.

Only generic model assets and documentation were copied here. The delivery folder is not mounted publicly. Model size is about17.08 MB; recording FPS and mobile performance are unverified.
