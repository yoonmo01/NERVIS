import assert from 'node:assert/strict'
import test from 'node:test'
import { CUE_FILES, playLocalCue } from '../src/fixedCues.ts'

function fakeAudio() {
  return { src: '', currentTime: 0, muted: true, onended: null as (() => void) | null,
    onerror: null as (() => void) | null, paused: false,
    play: () => Promise.resolve(), pause() { this.paused = true } }
}

test('missing cue resolves failure and releases handlers instead of blocking input', async () => {
  const audio = fakeAudio()
  const result = playLocalCue(audio as unknown as HTMLAudioElement, 'Yes_Sir.wav', new AbortController().signal)
  audio.onerror?.()
  assert.equal(await result, false)
  assert.equal(audio.paused, true)
  assert.equal(audio.onended, null)
})

test('abort stops a receipt cue and completion resolves only at audio end', async () => {
  const audio = fakeAudio(), controller = new AbortController()
  const cancelled = playLocalCue(audio as unknown as HTMLAudioElement, 'Right_Away_Sir.wav', controller.signal)
  controller.abort()
  assert.equal(await cancelled, false)
  const completed = playLocalCue(audio as unknown as HTMLAudioElement, 'Welcome_Back_Sir.wav', new AbortController().signal)
  audio.onended?.()
  assert.equal(await completed, true)
  assert.equal(audio.onerror, null)
})

test('selected MP3 and MP4 pass directly to browser playback without WAV fallback', async () => {
  for (const file of [CUE_FILES.welcome, 'Yes_Sir_V2.mp4'] as const) {
    const audio = fakeAudio()
    const result = playLocalCue(audio as unknown as HTMLAudioElement, file, new AbortController().signal)
    assert.equal(audio.src, `/audio/cues/${file}`)
    audio.onended?.()
    assert.equal(await result, true)
  }
})
