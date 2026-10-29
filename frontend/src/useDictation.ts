import { useEffect, useRef, useState } from 'react'
import { Dictation } from './stt.ts'
import type { DictationState } from './stt.ts'
import workletUrl from './microphone-worklet.js?url'

export function useDictation(enabled: boolean, onFinal: (text: string) => void) {
  const [state, setState] = useState<DictationState>({ phase: 'off', partial: '', error: '' })
  const final = useRef(onFinal)
  final.current = onFinal
  const session = useRef<Dictation | null>(null)
  useEffect(() => {
    const current = new Dictation(setState, text => final.current(text), 1500)
    session.current = current
    const end = () => current.cancel()
    const hide = () => { if (document.hidden) end() }
    window.addEventListener('pagehide', end)
    document.addEventListener('visibilitychange', hide)
    return () => {
      current.cancel(); session.current = null
      window.removeEventListener('pagehide', end)
      document.removeEventListener('visibilitychange', hide)
    }
  }, [])
  useEffect(() => { if (!enabled) session.current?.cancel() }, [enabled])
  return { ...state, active: ['starting', 'listening', 'stopping'].includes(state.phase),
    start: () => { void session.current?.start(workletUrl) }, stop: () => session.current?.stop() }
}
