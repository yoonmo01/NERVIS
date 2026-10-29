import { useEffect, useRef, useState } from 'react'
import { DoubleClap, isWakePhrase } from './activation.ts'
import { Dictation } from '../speech/stt.ts'
import workletUrl from '../speech/microphone-worklet.js?url'
import { CUE_FILES, playLocalCue } from './fixedCues.ts'
import type { CueFile } from './fixedCues.ts'

export function useActivation(started: boolean, canWake: boolean, onClap: () => void, onWake: () => void) {
  const [armed, setArmed] = useState(false)
  const [notice, setNotice] = useState('')
  const [greeting, setGreeting] = useState(false)
  const actions = useRef({ onClap, onWake, canWake })
  actions.current = { onClap, onWake, canWake }
  const wake = useRef<Dictation | null>(null)
  const cue = useRef<HTMLAudioElement | null>(null)
  const generation = useRef(0)
  const busy = useRef(false)
  const clapCleanup = useRef<(() => void) | null>(null)
  const cueRequest = useRef<AbortController | null>(null)

  const stop = () => {
    generation.current++; busy.current = false
    cueRequest.current?.abort(); cueRequest.current = null
    clapCleanup.current?.(); clapCleanup.current = null
    wake.current?.cancel(); wake.current = null
    if (cue.current) { cue.current.onended = cue.current.onerror = null; cue.current.pause(); cue.current.currentTime = 0 }
    setGreeting(false); setArmed(false)
  }
  const playCue = async (file: CueFile, after?: () => void): Promise<void> => {
    if (busy.current) return Promise.resolve()
    busy.current = true; wake.current?.cancel(); setGreeting(true); setNotice('')
    const current = ++generation.current
    const audio = cue.current ?? new Audio()
    cue.current = audio
    const request = new AbortController()
    cueRequest.current = request
    const ok = await playLocalCue(audio, file, request.signal)
    if (current !== generation.current) return
    cueRequest.current = null; busy.current = false; setGreeting(false)
    setNotice(ok ? '' : `${file} 재생 실패 · 파일과 브라우저 음성 권한을 확인해 주세요. 다음 단계는 계속 진행합니다.`)
    after?.()
  }
  const begin = () => {
    if (busy.current) return
    actions.current.onClap()
    void playCue(CUE_FILES.welcome)
  }
  const activate = () => {
    if (!actions.current.canWake || busy.current) return
    void playCue(CUE_FILES.wake, () => actions.current.onWake())
  }
  const activateRef = useRef(activate)
  activateRef.current = activate
  const beginRef = useRef(begin)
  beginRef.current = begin
  const arm = async () => {
    stop()
    const current = generation.current
    try {
      const audio = cue.current ?? new Audio(`/audio/cues/${CUE_FILES.welcome}`)
      cue.current = audio; audio.src = `/audio/cues/${CUE_FILES.welcome}`; audio.muted = true
      // Prime the same media element during the user's click for later wake playback.
      await audio.play(); audio.pause(); audio.currentTime = 0; audio.muted = false
      if (current !== generation.current) return
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      stream.getTracks().forEach(track => track.stop())
      if (current !== generation.current) return
      setNotice(''); setArmed(true)
    } catch (error) {
      if (current !== generation.current) return
      setNotice(error instanceof DOMException && error.name === 'NotAllowedError'
        ? '마이크 또는 음성 재생 권한을 허용한 뒤 NERVIS 깨우기를 눌러 주세요.'
        : `마이크 연결과 ${CUE_FILES.welcome} 파일을 확인한 뒤 다시 준비해 주세요.`)
    }
  }

  useEffect(() => {
    const hide = () => { if (document.hidden) { stop(); setNotice('') } }
    const leave = () => stop()
    document.addEventListener('visibilitychange', hide); window.addEventListener('pagehide', leave)
    return () => { stop(); document.removeEventListener('visibilitychange', hide); window.removeEventListener('pagehide', leave) }
  }, [])

  useEffect(() => {
    if (!armed || started) return
    let cancelled = false, stream: MediaStream | null = null, context: AudioContext | null = null
    let source: MediaStreamAudioSourceNode | null = null, worklet: AudioWorkletNode | null = null
    const cleanup = () => {
      cancelled = true
      if (worklet) { worklet.port.onmessage = null; worklet.port.close(); worklet.disconnect() }
      source?.disconnect(); stream?.getTracks().forEach(track => track.stop())
      if (context) void context.close().catch(() => {})
    }
    clapCleanup.current = cleanup
    void (async () => {
      try {
        const acquired = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false }, video: false })
        if (cancelled) { acquired.getTracks().forEach(track => track.stop()); return }
        stream = acquired
        stream.getTracks().forEach(track => { track.onended = () => { if (!cancelled) { cleanup(); setArmed(false); setNotice('마이크 연결이 종료됐습니다. 다시 준비해 주세요.') } } })
        context = new AudioContext(); await context.resume()
        if (cancelled) return
        await context.audioWorklet.addModule(workletUrl)
        if (cancelled) return
        const detector = new DoubleClap()
        worklet = new AudioWorkletNode(context, 'nervis-microphone')
        worklet.port.onmessage = event => {
          if (cancelled) return
          const pcm = new Int16Array(event.data)
          let sum = 0, peak = 0
          for (const value of pcm) { const x = value / 32768; sum += x * x; peak = Math.max(peak, Math.abs(x)) }
          if (detector.feed(Math.sqrt(sum / Math.max(1, pcm.length)), peak, performance.now())) {
            cleanup(); beginRef.current()
          }
        }
        source = context.createMediaStreamSource(stream); source.connect(worklet); worklet.connect(context.destination)
      } catch {
        if (!cancelled) { cleanup(); setArmed(false); setNotice('박수 감지 마이크를 열지 못했습니다. 다시 준비해 주세요.') }
      }
    })()
    return cleanup
  }, [armed, started])

  useEffect(() => {
    if (!armed || !started || !canWake || greeting) return
    let cancelled = false, timer: ReturnType<typeof setTimeout> | undefined
    const current = new Dictation(state => {
      if (cancelled) return
      if (state.partial && isWakePhrase(state.partial)) activateRef.current()
      if (state.phase === 'error') { setNotice(state.error); setArmed(false) }
      if (state.phase === 'off' && !busy.current) timer = setTimeout(() => { if (!cancelled) void current.start(workletUrl) }, 500)
    }, text => { if (!cancelled && isWakePhrase(text)) activateRef.current() }, 0, 'en')
    wake.current = current
    void current.start(workletUrl)
    return () => { cancelled = true; clearTimeout(timer); current.cancel(); if (wake.current === current) wake.current = null }
  }, [armed, started, canWake, greeting])

  return { armed, greeting, notice, arm, stop, activate, begin,
    acknowledge: () => playCue(CUE_FILES.receipt) }
}
