import { useEffect, useRef, useState } from 'react'
import { SpeechPlayer } from './tts.ts'
import type { SpeechState, VoiceProfile } from './tts.ts'

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
    play: (text: string, voice: VoiceProfile) => player.current?.play(text, voice), stop: () => player.current?.stop() }
}
