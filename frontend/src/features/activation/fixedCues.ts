type CueName = 'Welcome_Back_Sir' | 'Yes_Sir' | 'Right_Away_Sir'
export type CueFile = `${CueName}${'' | '_V2'}.${'wav' | 'mp3' | 'mp4' | 'm4a'}`

// Explicit selection avoids falling back to the previous cloned voice recordings.
export const CUE_FILES = {
  welcome: 'Welcome_Back_Sir_V2.mp3',
  wake: 'Yes_Sir_V2.mp3',
  receipt: 'Right_Away_Sir_V2.mp3',
} satisfies Record<string, CueFile>

export function playLocalCue(audio: HTMLAudioElement, file: CueFile, signal: AbortSignal): Promise<boolean> {
  if (signal.aborted) return Promise.resolve(false)
  return new Promise(resolve => {
    let finished = false
    const finish = (ok: boolean) => {
      if (finished) return
      finished = true; clearTimeout(timer)
      signal.removeEventListener('abort', abort)
      audio.onended = audio.onerror = null; audio.pause()
      resolve(ok)
    }
    const abort = () => finish(false)
    const timer = setTimeout(() => finish(false), 15000)
    signal.addEventListener('abort', abort, { once: true })
    audio.onended = () => finish(true)
    audio.onerror = () => finish(false)
    try {
      audio.src = `/audio/cues/${file}`; audio.currentTime = 0; audio.muted = false
      void audio.play().catch(() => finish(false))
    } catch { finish(false) }
  })
}
