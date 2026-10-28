import { useEffect, useRef, useState } from 'react'
import { SpeechPlayer } from './tts.ts'
import type { SpeechState } from './tts.ts'

export function useSpeech() {
  const [state, setState] = useState<SpeechState>({ phase: 'idle', error: '' })
  const player = useRef<SpeechPlayer | null>(null)
  const level = useRef(0)
  useEffect(() => {
    const current = new SpeechPlayer(setState)
    current.level = level; player.current = current
    const stop = () => current.stop()
    const hide = () => { if (document.hidden) stop() }
    window.addEventListener('pagehide', stop); document.addEventListener('visibilitychange', hide)
    return () => {
      current.stop(); player.current = null
      window.removeEventListener('pagehide', stop); document.removeEventListener('visibilitychange', hide)
    }
  }, [])
  return { ...state, level, active: state.phase === 'preparing' || state.phase === 'speaking',
    prepare: () => {
      // Audio availability must not prevent the text request from running.
      try { void player.current?.prepare().catch(() => {}) } catch { /* play reports the audio error. */ }
    },
    play: (text: string) => document.hidden ? undefined : player.current?.play(text), stop: () => player.current?.stop() }
}
