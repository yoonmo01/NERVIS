# ElevenLabs response speech

Select the adapter in the existing root `C:\NERVIS\.env` (not the frontend and
not `.env.local`). OS environment variables take precedence. Do not share keys
in chat or commit them.

```dotenv
NERVIS_TTS_BACKEND=elevenlabs
ELEVENLABS_API_KEY=YOUR_PRIVATE_KEY
ELEVENLABS_MODEL_ID=eleven_v3
ELEVENLABS_VOICE_ID=YOUR_SAVED_KOREAN_VOICE_ID
```

`model_id` is the synthesis engine. Voice Design creates a saved voice, whose
`voice_id` is separate from its displayed name (for example NERVIS_KO). In My
Voices, open the voice's three-dot menu and choose Copy voice ID. The sample
`21m00Tcm4TlvDq8ikWAM` in an SDK example is not the user's custom voice ID.

The default engine is `eleven_v3`, matching the user's example. Compatibility,
account access, latency and preferred voice quality have not been live-tested.
If comparing models, use an ID supported by the same saved voice and account;
do not silently fall back to another engine or incur another generation charge.

The adapter uses existing httpx and python-dotenv, so it does not require the
ElevenLabs SDK. If installing that SDK separately, use the project's `.venv`.
There is no need to execute the sample `output.mp3` script to configure NERVIS.

The single request converts the whole response using a fixed HTTPS endpoint,
`POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=pcm_24000`.
The existing relay receives PCM16 mono 24 kHz, with a 180-second bound, and the
frontend keeps its full-buffer playback, output-level visualization, ownership,
stop controls and analysis-screen preparation. No audio file is written. No
startup generation, voice/model listing, credit query, retry or provider fallback
is added. A missing/invalid configuration reports a local error.

Only the response text is sent to ElevenLabs, with the same approved summary
boundary as the existing external TTS. No original images, masks, complete time
series, paths or credentials are added to the text. Local Korean STT, clap/wake
detection and the three fixed WAV cues are unchanged. This switches dynamic
Korean response speech only. External provider logging follows the account's
terms; the adapter does not claim enterprise zero-retention behavior.

After editing `.env`, restart the backend and refresh the browser. The frontend
does not read the root environment. A user-triggered response, including a dummy
preview, will make a paid TTS request. Failure is not automatically retried.
Tests were added with mock transport but not executed, and no build, live API,
browser checks or server restarts were performed at the user's request.

Official references: [voice ID](https://elevenlabs.io/docs/help-center/technical/how-do-i-find-the-voice-id-of-my-voices-via-the-website-and-api),
[conversion API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert).
