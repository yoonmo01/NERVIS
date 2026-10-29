import { audioLevel } from './model.ts'
import type { SpeechSegment } from './presentation.ts'
import type { RequestOwner } from './chatStream.ts'

export type SpeechState = { phase: 'idle' | 'preparing' | 'ready' | 'speaking' | 'error'; error: string; target?: string | null; synchronized?: boolean; owner?: RequestOwner; preparedMs?: number }

export function speechText(value: string): string {
  return value.replace(/&#(?:x20|32);/gi, ' ').replace(/```[\s\S]*?```/g, ' ').replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)/gm, '')
    .replace(/\\([*~])/g, '$1').replace(/[*_`]/g, '')
    .replace(/(?<![\d:])([01]?\d|2[0-3]):([0-5]\d)(?![\d:])/g, (_, hour: string, minute: string) => `${Number(hour)}시${Number(minute) ? ` ${Number(minute)}분` : ''}`)
    .replace(/(\d+시(?: \d+분)?)\s*[~～–—-]\s*(\d+시(?: \d+분)?)/g, '$1에서 $2')
    .replace(/([−-]?\d+(?:\.\d+)?)\s*[~～–—]\s*([−-]?\d+(?:\.\d+)?)\s*(?:°\s*C|℃)/gi, '$1도에서 $2도')
    .replace(/([−-]?\d+(?:\.\d+)?)\s*(?:°\s*C|℃)/gi, '$1도')
    .replace(/([−-]?\d+(?:\.\d+)?)도\s*[~～–—]\s*([−-]?\d+(?:\.\d+)?)도/g, '$1도에서 $2도')
    .replace(/([−-]?\d+(?:\.\d+)?)\s*°\s*F/gi, '화씨 $1도')
    .replace(/\s+/g, ' ').trim()
}

export function pcmSamples(bytes: ArrayBuffer): Float32Array {
  if (!bytes.byteLength || bytes.byteLength % 2) throw new Error('음성 PCM 형식이 올바르지 않습니다.')
  const input = new DataView(bytes), samples = new Float32Array(bytes.byteLength / 2)
  for (let i = 0; i < samples.length; i++) samples[i] = input.getInt16(i * 2, true) / 32768
  return samples
}

export function waveAudio(buffer: AudioBuffer): Blob {
  const bytes = new ArrayBuffer(44 + (buffer.length + Math.round(buffer.sampleRate * 0.5)) * 2), view = new DataView(bytes)
  const label = (offset: number, text: string) => { for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i)) }
  label(0, 'RIFF'); view.setUint32(4, bytes.byteLength - 8, true); label(8, 'WAVE'); label(12, 'fmt ')
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true)
  view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * 2, true)
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); label(36, 'data'); view.setUint32(40, bytes.byteLength - 44, true)
  const samples = buffer.getChannelData(0)
  for (let i = 0; i < samples.length; i++) {
    const sample = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(44 + i * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true)
  }
  return new Blob([bytes], { type: 'audio/wav' })
}

export class SpeechPlayer {
  state: SpeechState = { phase: 'idle', error: '' }
  level = { current: 0 }
  private update: (value: SpeechState) => void
  private context: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private socket: WebSocket | null = null
  private source: MediaElementAudioSourceNode | null = null
  private audio: HTMLAudioElement | null = null
  private audioUrl: string | null = null
  private frame = 0
  private timer: ReturnType<typeof setTimeout> | undefined
  private generation = 0
  private sampleRate = 0
  private sampleCount = 0
  private chunks: Float32Array[] = []
  private buffer: AudioBuffer | null = null
  private owner: RequestOwner | undefined

  constructor(update: (value: SpeechState) => void) { this.update = update }
  private set(value: SpeechState) { this.state = { ...value, ...(this.owner ? { owner: this.owner } : {}) }; this.update(this.state) }
  private deadline() {
    clearTimeout(this.timer)
    this.timer = setTimeout(() => this.fail('음성 대기 시간이 지났습니다. TTS 연결 상태를 확인해 주세요. 자동 재시도하지 않습니다.'), 120000)
  }
  private release() {
    this.generation++
    clearTimeout(this.timer); cancelAnimationFrame(this.frame); this.level.current = 0
    if (this.audio) { this.audio.onended = this.audio.onerror = null; this.audio.pause(); this.audio.removeAttribute('src'); this.audio.load(); this.audio = null }
    this.source?.disconnect(); this.source = null
    if (this.audioUrl) { URL.revokeObjectURL(this.audioUrl); this.audioUrl = null }
    this.chunks = []; this.buffer = null; this.sampleCount = 0
    this.analyser?.disconnect(); this.analyser = null
    if (this.context) { void this.context.close().catch(() => {}); this.context = null }
    if (this.socket) {
      this.socket.onopen = this.socket.onmessage = this.socket.onerror = this.socket.onclose = null
      this.socket.close(); this.socket = null
    }
  }
  private fail(message: string) { this.release(); this.set({ phase: 'error', error: message }) }
  stop() { this.release(); this.set({ phase: 'idle', error: '' }) }
  prepare() {
    if (!this.context) this.context = new AudioContext()
    return this.context.resume()
  }
  async start(expected?: RequestOwner) {
    if (this.state.phase !== 'ready' || !this.buffer || !this.context) return
    if (expected && (expected.request_id !== this.owner?.request_id || expected.session_id !== this.owner?.session_id)) return
    const generation = this.generation, context = this.context, buffer = this.buffer
    const current = () => this.generation === generation
    // Claim synchronously so repeated ready notifications cannot start duplicate playback.
    this.set({ ...this.state, phase: 'speaking' })
    try {
      await context.resume()
      if (!current()) return
      if (context.state === 'suspended') throw new Error('자동 음성 재생이 차단됐습니다. 이 사이트의 소리를 허용해 주세요.')
      const analyser = context.createAnalyser()
      analyser.fftSize = 256; analyser.connect(context.destination); this.analyser = analyser
      const samples = new Float32Array(analyser.fftSize)
      const tick = () => {
        if (!current()) return
        analyser.getFloatTimeDomainData(samples); this.level.current = audioLevel(samples)
        this.frame = requestAnimationFrame(tick)
      }
      this.audioUrl = URL.createObjectURL(waveAudio(buffer))
      const audio = new Audio(this.audioUrl)
      audio.playbackRate = 1.15; audio.preservesPitch = true; this.audio = audio
      const source = context.createMediaElementSource(audio)
      source.connect(analyser); this.source = source; this.buffer = null
      audio.onended = () => {
        if (!current()) return
        try { this.socket?.send(JSON.stringify({ type: 'playback.finished', ...this.owner })) } catch { /* Playback already finished. */ }
        this.release(); this.set({ phase: 'idle', error: '' })
      }
      audio.onerror = () => { if (current()) this.fail('준비된 응답 음성을 재생하지 못했습니다.') }
      await audio.play()
      if (!current()) return
      tick()
    } catch (error) {
      if (current()) this.fail(error instanceof Error ? error.message : '음성을 재생하지 못했습니다.')
    }
  }
  async play(value: string, _segments: SpeechSegment[] = [], owner?: RequestOwner, deferStart = false) {
    if (['preparing', 'ready', 'speaking'].includes(this.state.phase)) return
    const generation = ++this.generation, started = performance.now()
    const current = () => this.generation === generation
    this.owner = owner
    this.set({ phase: 'preparing', error: '', synchronized: false })
    this.sampleRate = 0; this.sampleCount = 0; this.chunks = []; this.buffer = null
    this.deadline()
    try {
      const text = speechText(value)
      if (!text || text.length > 2000) throw new Error('읽을 응답은 1~2000자여야 합니다. 화면의 응답은 그대로 유지됩니다.')
      const context = this.context ?? new AudioContext()
      this.context = context
      await context.resume()
      if (!current()) return
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/tts/stream`)
      this.socket = socket; socket.binaryType = 'arraybuffer'
      // One full-text request. Incoming PCM is held until the entire utterance is complete.
      socket.onopen = () => { if (current()) socket.send(JSON.stringify({ text, ...owner })) }
      socket.onerror = () => { if (current()) this.fail('NERVIS 음성 연결에 실패했습니다. 백엔드 서버를 확인해 주세요.') }
      socket.onclose = () => { if (current()) this.fail('음성 연결이 완료 전에 끊겼습니다. 자동 재시도하지 않습니다.') }
      socket.onmessage = event => {
        if (!current()) return
        try {
          if (event.data instanceof ArrayBuffer) {
            if (!this.sampleRate || this.state.phase !== 'preparing') throw new Error('음성 스트림 순서가 올바르지 않습니다.')
            const pcm = pcmSamples(event.data)
            this.sampleCount += pcm.length
            if (this.sampleCount > this.sampleRate * 180) throw new Error('음성 길이 제한을 초과했습니다.')
            this.chunks.push(pcm); this.deadline()
          } else {
            const message = JSON.parse(event.data)
            if (owner && (message.request_id !== owner.request_id || message.session_id !== owner.session_id)) throw new Error('다른 요청의 음성 응답이 도착했습니다.')
            if (this.state.phase !== 'preparing') throw new Error('음성 스트림 순서가 올바르지 않습니다.')
            this.deadline()
            if (message.type === 'start') {
              if (this.sampleRate || !Number.isInteger(message.sample_rate) || message.sample_rate < 8000 || message.sample_rate > 48000 || message.channels !== 1 || message.format !== 'pcm16') throw new Error('지원하지 않는 음성 형식입니다.')
              this.sampleRate = message.sample_rate
            } else if (message.type === 'done') {
              if (!this.sampleRate || !this.sampleCount) throw new Error('빈 음성 응답입니다.')
              const buffer = context.createBuffer(1, this.sampleCount, this.sampleRate), samples = buffer.getChannelData(0)
              let offset = 0
              for (const chunk of this.chunks) { samples.set(chunk, offset); offset += chunk.length }
              this.chunks = []; this.buffer = buffer; clearTimeout(this.timer)
              this.set({ phase: 'ready', error: '', synchronized: false, preparedMs: Math.round(performance.now() - started) })
              if (!deferStart) void this.start(owner)
            } else if (message.type === 'error') {
              const errors: Record<string, string> = {
                model_missing: 'VoiceStudio에 설치된 OmniVoice 모델을 확인해 주세요. 자동 다운로드하지 않습니다.',
                model_loading: 'OmniVoice를 메모리에 로드하지 못했습니다. VoiceStudio의 모델 상태를 확인해 주세요.',
                voice_missing: '설정한 한국어 음성 프로필을 찾지 못했습니다. 프로필 이름과 언어를 확인해 주세요.',
              }
              throw new Error(errors[message.code] ?? (typeof message.message === 'string' && message.message.length <= 300 ? message.message : '응답 음성 생성에 실패했습니다. TTS 설정과 연결 상태를 확인해 주세요.'))
            }
          }
        } catch (error) { this.fail(error instanceof Error ? error.message : '음성 응답을 읽지 못했습니다.') }
      }
    } catch (error) {
      if (current()) this.fail(error instanceof Error ? error.message : '음성을 준비하지 못했습니다.')
    }
  }
}
