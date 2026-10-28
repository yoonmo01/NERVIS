import { audioLevel } from './model.ts'

export type VoiceProfile = 'JARVIS' | 'JARVIS_2'
export type SpeechState = { phase: 'idle' | 'preparing' | 'speaking' | 'error'; error: string }

export function speechText(value: string): string {
  return value.replace(/```[\s\S]*?```/g, ' ').replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)/gm, '')
    .replace(/[*_`]/g, '').replace(/\s+/g, ' ').trim()
}

export function pcmSamples(bytes: ArrayBuffer): Float32Array {
  if (!bytes.byteLength || bytes.byteLength % 2) throw new Error('음성 PCM 형식이 올바르지 않습니다.')
  const input = new DataView(bytes), samples = new Float32Array(bytes.byteLength / 2)
  for (let i = 0; i < samples.length; i++) samples[i] = input.getInt16(i * 2, true) / 32768
  return samples
}

export class SpeechPlayer {
  state: SpeechState = { phase: 'idle', error: '' }
  level = { current: 0 }
  private update: (value: SpeechState) => void
  private context: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private socket: WebSocket | null = null
  private sources = new Set<AudioBufferSourceNode>()
  private frame = 0
  private timer: ReturnType<typeof setTimeout> | undefined
  private generation = 0
  private sampleRate = 0
  private nextAt = 0
  private generated = false

  constructor(update: (value: SpeechState) => void) { this.update = update }
  private set(value: SpeechState) { this.state = value; this.update(value) }
  private deadline() {
    clearTimeout(this.timer)
    this.timer = setTimeout(() => this.fail('음성 대기 시간이 지났습니다. VoiceStudio 상태를 확인해 주세요.'), 120000)
  }
  private release() {
    this.generation++
    clearTimeout(this.timer); cancelAnimationFrame(this.frame); this.level.current = 0
    for (const source of this.sources) {
      source.onended = null
      try { source.stop() } catch { /* A completed source needs no stop. */ }
      source.disconnect()
    }
    this.sources.clear()
    this.analyser?.disconnect(); this.analyser = null
    if (this.context) { void this.context.close().catch(() => {}); this.context = null }
    if (this.socket) {
      this.socket.onopen = this.socket.onmessage = this.socket.onerror = this.socket.onclose = null
      this.socket.close(); this.socket = null
    }
  }
  private fail(message: string) { this.release(); this.set({ phase: 'error', error: message }) }
  stop() { this.release(); this.set({ phase: 'idle', error: '' }) }
  private finish() {
    if (!this.generated || this.sources.size) return
    try { this.socket?.send(JSON.stringify({ type: 'playback.finished' })) } catch { /* Playback already finished. */ }
    this.release(); this.set({ phase: 'idle', error: '' })
  }
  async play(value: string, voice: VoiceProfile) {
    if (this.state.phase === 'preparing' || this.state.phase === 'speaking') return
    this.stop()
    const generation = this.generation
    const current = () => this.generation === generation
    this.set({ phase: 'preparing', error: '' })
    this.sampleRate = 0; this.nextAt = 0; this.generated = false
    this.deadline()
    try {
      const text = speechText(value)
      if (!text || text.length > 2000) throw new Error('읽을 응답은 1~2000자여야 합니다. 화면의 응답은 그대로 유지됩니다.')
      const context = new AudioContext()
      this.context = context
      await context.resume()
      if (!current()) return
      if (context.state === 'suspended') throw new Error('브라우저에서 소리를 허용한 뒤 응답 읽기를 다시 눌러 주세요.')
      const analyser = context.createAnalyser()
      analyser.fftSize = 256; analyser.connect(context.destination); this.analyser = analyser
      const samples = new Float32Array(analyser.fftSize)
      const tick = () => {
        if (!current()) return
        analyser.getFloatTimeDomainData(samples); this.level.current = audioLevel(samples)
        this.frame = requestAnimationFrame(tick)
      }
      tick()
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/tts/stream`)
      this.socket = socket; socket.binaryType = 'arraybuffer'
      socket.onopen = () => { if (current()) socket.send(JSON.stringify({ text, voice })) }
      socket.onerror = () => this.fail('로컬 TTS 서버 연결에 실패했습니다. VoiceStudio와 NERVIS 서버를 확인해 주세요.')
      socket.onclose = () => this.fail('음성 연결이 완료 전에 끊겼습니다. 자동 재시도하지 않습니다.')
      socket.onmessage = event => {
        if (!current()) return
        try {
          this.deadline()
          if (event.data instanceof ArrayBuffer) {
            if (!this.sampleRate || this.generated) throw new Error('음성 스트림 순서가 올바르지 않습니다.')
            const pcm = pcmSamples(event.data)
            const buffer = context.createBuffer(1, pcm.length, this.sampleRate)
            buffer.getChannelData(0).set(pcm)
            const source = context.createBufferSource()
            source.buffer = buffer; source.connect(analyser)
            const start = Math.max(context.currentTime + .06, this.nextAt)
            if (start + buffer.duration - context.currentTime > 180) throw new Error('음성 재생 대기 길이를 초과했습니다.')
            this.nextAt = start + buffer.duration
            this.sources.add(source)
            source.onended = () => { this.sources.delete(source); source.disconnect(); this.finish() }
            source.start(start)
            if (this.state.phase !== 'speaking') this.set({ phase: 'speaking', error: '' })
          } else {
            const message = JSON.parse(event.data)
            if (message.type === 'start') {
              if (this.sampleRate || !Number.isInteger(message.sample_rate) || message.sample_rate < 8000 || message.sample_rate > 48000
                || message.channels !== 1 || message.format !== 'pcm16') throw new Error('지원하지 않는 음성 형식입니다.')
              this.sampleRate = message.sample_rate
            } else if (message.type === 'done') {
              if (!this.sampleRate) throw new Error('빈 음성 응답입니다.')
              this.generated = true; clearTimeout(this.timer); this.finish()
            } else if (message.type === 'error') {
              throw new Error('로컬 음성 생성에 실패했습니다. VoiceStudio의 OmniVoice·한국어 프로필·메모리 상태를 확인해 주세요.')
            }
          }
        } catch (error) { this.fail(error instanceof Error ? error.message : '음성 스트림을 읽지 못했습니다.') }
      }
    } catch (error) {
      if (current()) this.fail(error instanceof Error ? error.message : '음성을 시작하지 못했습니다.')
    }
  }
}
