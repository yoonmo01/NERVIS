# Fixed voice cues

Place the manually exported English voice files here:

- `Welcome_Back_Sir.wav`: "Welcome back, sir." (startup intro)
- `Yes_Sir.wav`: "Yes, sir?" (wake phrase, before dictation)
- `Right_Away_Sir.wav`: "Right away, sir." (accepted request)

Current selected files are `Welcome_Back_Sir_V2.mp3`, `Yes_Sir_V2.mp3`,
and `Right_Away_Sir_V2.mp3`, as supplied by the user. WAV conversion is unnecessary.
The browser player also accepts MP4/M4A audio; if supplying those files, update the
three filenames in `frontend/src/fixedCues.ts` (`CUE_FILES`) and refresh the page.
MP4 must contain a browser-supported audio track; an extension alone does not
guarantee codec support. Existing WAV files are kept but are not fallback sources.
Use short clips without background music and trim unnecessary silence.
These files are connected to local browser playback. Replace recordings with
rights-cleared voices using the same filenames; refresh the browser afterward.
Generated audio is ignored by Git. Only intentionally public fixed phrases belong
here: Vite serves this directory to the browser. Never place credentials, original
brain data, personal recordings, or analysis results here.
