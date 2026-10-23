# Current hologram preview

The viewer loads `nervis-hologram-brain-narrow-gap.glb`, `hologram-region-map-narrow-gap.json` and `hologram-render-contract-narrow-gap.json`. Earlier model files remain available for rollback.

The model contains two cortex shells, twenty selectable cortical regions, and cerebellum and brainstem context meshes. Region boundaries illustrate a general brain; they do not represent the supplied subject's exact anatomy. No supplied MRI, mask or time series is embedded in the model.

The hemisphere gap is half the preceding version's gap. Colors, translucent surfaces and particles remain controlled by the web renderer. Each selected region follows one signal value across its surface and particles, independently of the other regions and hemisphere. Selection remains visible at zero; displayed signal magnitude is not proof of increased neural activation.

The default camera uses an oblique view. Drag rotates vertically and horizontally at the default speed; Q/E adjusts screen tilt. View presets and reset remain available.

The GLSL files and rendering contract describe surface attributes and display styling. Blender/Cycles and WebGL appearances are not claimed to be pixel-identical. Recording frame rate and mobile performance remain unverified.
