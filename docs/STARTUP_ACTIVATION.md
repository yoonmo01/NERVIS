# Startup activation

2026-10-29 cue selection update: current actual supplied replacements are the
three `*_V2.mp3` files. `frontend/src/fixedCues.ts` CUE_FILES selects them for all
startup, wake and receipt playback, including permission priming. MP4/M4A can
also be selected when their audio codecs are supported by the browser. The old
WAVs are retained without fallback. Historical WAV references below describe
the cue roles; current filenames are defined by CUE_FILES. No conversion occurs.

The browser initially holds the title. Click **시작 준비** once to permit the
microphone and prime the supplied `Welcome_Back_Sir.wav` media element. Two short
loud bursts 180–850 ms apart start the existing intro and play
`Welcome_Back_Sir.wav` once for that startup. This is an amplitude and
duration heuristic, not a trained clap classifier; other impacts can trigger it.
Headset microphone gain and noise filtering may prevent detection.

After the intro, the existing Korean local Turbo STT listens for `HEY NERVIS`
or supported Korean phonetic spellings. No browser cloud speech API, new model,
or external request is used. This is transcript-based wake detection, so latency
and recognition accuracy depend on the local STT. Its transcript is discarded.
The existing bounded STT recording is restarted after normal completion while
waiting; recognition errors stop waiting and require explicit rearming.

On detection, stop the wake session, play `Yes_Sir.wav`, then open
the shared editable dictation input. Existing drafts are appended to, never
replaced. After speech begins, 1.5 seconds below the microphone energy threshold
ends recording and waits for the final transcript. This threshold is a simple
local energy gate; noise can keep it open and quiet speech can end it early.
No automatic submission is added. Actual response TTS still uses the existing
configured engine. The server's `request.started` SSE event triggers
`Right_Away_Sir.wav` at most once per submitted request. Preview requests trigger
it after successful preview retrieval. Processing continues while this cue plays,
and result/error TTS waits for it to finish. Failed/missing cues are reported and
do not block the next step; each cue has a 15-second bound. Stopping/exit releases
cue waiters as well as the media element. No extra TTS generation requests occur.

Wake listening pauses while input is open, a request or response is active, or
history is open. Close the input to resume armed wake waiting. Direct input
buttons or the shortcut disable wake waiting; re-enable it with its button.
Hidden tabs/page exit stop activation monitoring and the fixed cue. This does
not cancel existing AI/HAI response playback. A user must rearm monitoring on return.

**Ctrl+Shift+Space** starts the intro while waiting, or toggles question dictation
after startup. It works only while the page receives keyboard events. Existing
request locks remain in force.

Manual acceptance sequence: reload → prepare/permission → two claps → intro →
startup welcome → "Hey NERVIS" → "Yes, sir?" finishes → listening indicator →
Korean question → 1.5 s silence → editable final text → explicit send → receipt
cue → existing response TTS. Also check permission refusal,
unplugging, wake false positives, shortcut, draft preservation and hiding the tab.
Implementation added without running tests, build, browser or live microphone
checks at the user's request. Real hardware behavior is not yet verified.

See `VOICE_CUE_RIGHTS.md` before using the supplied cloned voice in a submission.
