import { useCallback, useEffect, useRef, useState } from 'react'
import { audioLevel } from './model.ts'

export function useAudioPreview() {
  const [active, setActive] = useState(false)
  const [error, setError] = useState('')
  const level = useRef(0)
  const mounted = useRef(true)
  const current = useRef<{ context: AudioContext; oscillators: OscillatorNode[]; frame: number } | null>(null)

  const stop = useCallback(() => {
    const resource = current.current
    current.current = null
    level.current = 0
    if (resource) {
      cancelAnimationFrame(resource.frame)
      for (const oscillator of resource.oscillators) {
        oscillator.onended = null
        try { oscillator.stop() } catch { /* Already ended. */ }
        oscillator.disconnect()
      }
      void resource.context.close().catch(() => {})
    }
    if (mounted.current) setActive(false)
  }, [])

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; stop() }
  }, [stop])

  const play = useCallback(async () => {
    stop()
    setError('')
    try {
      const context = new AudioContext()
      const gain = context.createGain()
      const analyser = context.createAnalyser()
      analyser.fftSize = 256
      gain.connect(analyser)
      analyser.connect(context.destination)
      const oscillators = [176, 264].map(frequency => {
        const oscillator = context.createOscillator()
        oscillator.type = 'sine'
        oscillator.frequency.value = frequency
        oscillator.connect(gain)
        return oscillator
      })
      const resource = { context, oscillators, frame: 0 }
      current.current = resource
      await context.resume()
      if (current.current !== resource) return
      const start = context.currentTime
      gain.gain.setValueAtTime(0, start)
      const envelope = [0, 0.09, 0.025, 0.12, 0.01, 0.07, 0.13, 0.025, 0]
      envelope.forEach((value, i) => gain.gain.linearRampToValueAtTime(value, start + i * 0.45))
      const samples = new Float32Array(analyser.fftSize)
      const tick = () => {
        if (current.current !== resource) return
        analyser.getFloatTimeDomainData(samples)
        level.current = audioLevel(samples)
        resource.frame = requestAnimationFrame(tick)
      }
      oscillators[0].onended = stop
      for (const oscillator of oscillators) { oscillator.start(start); oscillator.stop(start + 3.65) }
      tick()
      setActive(true)
    } catch {
      stop()
      if (mounted.current) setError('오디오를 시작할 수 없습니다. 브라우저의 소리 권한을 확인해 주세요.')
    }
  }, [stop])

  return { active, level, play, stop, error }
}
