# TTS style review — 2026-10-29

[Google's model page](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts)
confirms `gemini-3.8-flash-tts` and turn-level style control.
[The native API guide](https://ai.google.dev/gemini-api/docs/speech-generation)
documents structured speech metadata and inline vocal tags. These are native
Google API capabilities, not proof that HAI's OpenAI-compatible route exposes them.

[HAI's public TTS reference](https://docs.mindlogic.ai/docs/hallym-ac/api-gateway/reference/audio-tts)
currently lists `model`, `input`, `voice`, `speakers`, with model examples up to
3.1 Flash TTS. It does not document 3.8 or a separate style/instructions field.
Actual account model access and forwarding remain unverified. No authenticated
model-list, balance, generation or test requests were made. Do not change the
active model or add unsupported fields based solely on native Google docs.

Suggested original voice direction if the supported route is confirmed:
"A calm, precise adult male assistant; low-mid register, restrained warmth,
clear Korean diction, a brisk conversational pace, and short natural pauses.
Use an original voice without imitating any identifiable actor or character."
This is a candidate direction, not a quality or licensing guarantee.

The existing `.env` model/voice and adapter remain unchanged in this review.
For the three fixed cues, recording the user's own voice avoids reliance on
the unresolved Fish Audio source described in `VOICE_CUE_RIGHTS.md`.
