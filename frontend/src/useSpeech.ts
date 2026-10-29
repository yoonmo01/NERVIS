import { useEffect, useRef, useState } from 'react'
import { SpeechPlayer } from './tts.ts'
import type { SpeechState } from './tts.ts'
import type { SpeechSegment } from './presentation.ts'
import type { RequestOwner } from './chatStream.ts'

export function useSpeech() {
  const [state, setState] = useState<SpeechState>({ phase: 'idle', error: '' })
  const player = useRef<SpeechPlayer | null>(null)
  const level = useRef(0)
  const owner = useRef<RequestOwner | null>(null)
  useEffect(() => {
    const current = new SpeechPlayer(value => {
      if (value.owner && (owner.current?.request_id !== value.owner.request_id || owner.current?.session_id !== value.owner.session_id)) return
      setState(value)
    })
    current.level = level; player.current = current
    const stop = () => current.stop()
    window.addEventListener('pagehide', stop)
    return () => {
      current.stop(); player.current = null
      window.removeEventListener('pagehide', stop)
    }
  }, [])
  return { ...state, level, active: state.phase === 'preparing' || state.phase === 'ready' || state.phase === 'speaking',
    claim: (next: RequestOwner | null) => {
      if (owner.current?.request_id !== next?.request_id) {
        player.current?.stop()
        setState({ phase: 'idle', error: '' })
      }
      owner.current = next
    },
    prepare: () => {
      // Audio availability must not prevent the text request from running.
      try { void player.current?.prepare().catch(() => {}) } catch { /* play reports the audio error. */ }
    },
    play: (text: string, segments: SpeechSegment[] = [], expected?: RequestOwner, deferStart = false) => {
      if (expected && (owner.current?.request_id !== expected.request_id || owner.current?.session_id !== expected.session_id)) return
      return player.current?.play(text, segments, expected, deferStart)
    }, start: (expected: RequestOwner) => {
      if (owner.current?.request_id === expected.request_id && owner.current?.session_id === expected.session_id) return player.current?.start(expected)
    }, stop: () => player.current?.stop() }
}
