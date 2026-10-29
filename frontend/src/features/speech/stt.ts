export type DictationState = { phase: 'off' | 'starting' | 'listening' | 'stopping' | 'error'; partial: string; error: string; device?: string }

export function appendTranscript(draft: string, text: string): string | null {
  text = text.trim()
  const joined = draft + (draft && text && !/\s$/.test(draft) ? ' ' : '') + text
  return joined.length <= 600 ? joined : null
}

export class Transcript {
  private committed = 0
  read(value: unknown): { partial?: string; final?: string; done?: boolean } {
    if (!value || typeof value !== 'object') throw new Error('로컬 STT 응답 형식을 확인해 주세요.')
    const message = value as Record<string, unknown>
    if (message.type === 'error') throw new Error('로컬 STT 인식 오류입니다. 앱의 받아쓰기 모델 상태를 확인해 주세요.')
    if (message.type !== 'partial' && message.type !== 'final') return {}
    if (typeof message.text !== 'string' || message.text.length > 100000) throw new Error('로컬 STT 인식 결과 형식이 잘못됐습니다.')
    if (message.type === 'partial') return { partial: message.text }
    if (message.final_kind === 'utterance') { this.committed++; return { final: message.text } }
    let tail = message.text
    if (this.committed) {
      if (!Array.isArray(message.segments) || message.segments.length < this.committed
        || message.segments.some(s => !s || typeof s.text !== 'string')) throw new Error('로컬 STT 확정 요약을 확인할 수 없습니다. 기존 초안은 유지됩니다.')
      tail = message.segments.slice(this.committed).map(s => s.text).join(' ')
    }
    return { final: tail, done: true }
  }
}

export class Dictation {
  state: DictationState = { phase: 'off', partial: '', error: '' }
  private update: (state: DictationState) => void
  private commit: (text: string) => void
  private generation = 0
  private request: AbortController | null = null
  private stream: MediaStream | null = null
  private context: AudioContext | null = null
  private source: MediaStreamAudioSourceNode | null = null
  private worklet: AudioWorkletNode | null = null
  private socket: WebSocket | null = null
  private timer: ReturnType<typeof setTimeout> | undefined
  private silenceMs: number

  constructor(update: (state: DictationState) => void, commit: (text: string) => void, silenceMs = 0, private language: 'ko' | 'en' = 'ko') {
    this.update = update; this.commit = commit; this.silenceMs = silenceMs
  }
  private set(patch: Partial<DictationState>) { this.state = { ...this.state, ...patch }; this.update(this.state) }
  private deadline(ms: number, message: string) {
    clearTimeout(this.timer)
    this.timer = setTimeout(() => this.fail(message), ms)
  }
  private releaseAudio() {
    if (this.worklet) { this.worklet.port.onmessage = null; this.worklet.port.close(); this.worklet.disconnect(); this.worklet = null }
    this.source?.disconnect(); this.source = null
    this.stream?.getTracks().forEach(track => { track.onended = null; track.stop() }); this.stream = null
    if (this.context) { void this.context.close().catch(() => {}); this.context = null }
  }
  private release() {
    this.generation++
    clearTimeout(this.timer)
    this.request?.abort(); this.request = null
    this.releaseAudio()
    if (this.socket) {
      this.socket.onopen = this.socket.onmessage = this.socket.onerror = this.socket.onclose = null
      this.socket.close(); this.socket = null
    }
  }
  private fail(message: string) { this.release(); this.set({ phase: 'error', error: message }) }
  cancel() { this.release(); this.set({ phase: 'off', partial: '', error: '' }) }
  stop() {
    if (this.state.phase === 'starting') { this.cancel(); return }
    if (this.state.phase !== 'listening') return
    this.releaseAudio()
    this.set({ phase: 'stopping' })
    try { this.socket?.send(JSON.stringify({ type: 'input_audio.end' })) }
    catch { this.fail('로컬 STT 연결이 끊겼습니다. 확정된 초안은 유지됩니다.'); return }
    this.deadline(60000, '확정 문장 대기 시간이 지났습니다. 인식 중 문장을 확인하고 다시 시작해 주세요.')
  }
  async start(workletUrl: string) {
    if (['starting', 'listening', 'stopping'].includes(this.state.phase)) return
    this.release()
    const generation = this.generation
    const current = () => this.generation === generation
    this.set({ phase: 'starting', partial: '', error: '' })
    this.deadline(10000, '로컬 STT 서버에 연결하지 못했습니다. 127.0.0.1:8000 실행 상태를 확인해 주세요.')
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof AudioWorkletNode === 'undefined') throw new Error('이 브라우저에서 로컬 마이크 입력을 지원하지 않습니다. Chrome에서 localhost로 열어 주세요.')
      this.request = new AbortController()
      const response = await fetch('/api/stt/status', { signal: this.request.signal })
      if (!response.ok) throw new Error('NERVIS 로컬 STT 서버 연결에 실패했습니다.')
      const status = await response.json()
      if (!current()) return
      if (!status.ready || status.language !== 'ko') throw new Error('설치된 한국어 Turbo 모델을 확인해 주세요. 자동 다운로드하지 않습니다.')
      if (status.busy) throw new Error('다른 받아쓰기가 실행 중입니다. 종료 후 다시 켜 주세요.')
      clearTimeout(this.timer)
      this.request = null
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true }, video: false })
      if (!current()) { stream.getTracks().forEach(track => track.stop()); return }
      this.stream = stream
      stream.getTracks().forEach(track => { track.onended = () => this.fail('마이크 연결이 종료됐습니다. 헤드셋을 확인하고 다시 켜 주세요.') })
      const context = new AudioContext({ sampleRate: 16000 })
      this.context = context
      await context.resume()
      if (!current()) return
      if (context.sampleRate !== 16000) throw new Error('마이크의 16kHz 오디오 변환을 지원하지 않습니다.')
      await context.audioWorklet.addModule(workletUrl)
      if (!current()) return
      const worklet = new AudioWorkletNode(context, 'nervis-microphone')
      this.worklet = worklet
      const source = context.createMediaStreamSource(stream)
      this.source = source
      const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/stt/stream?language=${this.language}`)
      this.socket = socket
      const transcript = new Transcript()
      let speechSamples = 0, silentSamples = 0
      this.deadline(70000, '로컬 STT 모델 준비 시간이 지났습니다. 로컬 앱 상태를 확인해 주세요.')
      worklet.port.onmessage = event => {
        if (this.state.phase !== 'listening' || socket.readyState !== 1) return
        if (socket.bufferedAmount > 320000) { this.fail('음성 전송이 지연돼 마이크를 껐습니다. 서버 상태를 확인해 주세요.'); return }
        socket.send(event.data)
        if (this.silenceMs) {
          const pcm = new Int16Array(event.data)
          let power = 0
          for (const sample of pcm) power += (sample / 32768) ** 2
          if (Math.sqrt(power / Math.max(1, pcm.length)) > 0.012) { speechSamples += pcm.length; silentSamples = 0 }
          else if (speechSamples >= 1600) silentSamples += pcm.length
          if (silentSamples >= this.silenceMs * 16) this.stop()
        }
      }
      socket.onerror = () => this.fail('로컬 STT 연결에 실패했습니다. 로컬 앱과 프록시를 확인해 주세요.')
      socket.onclose = () => this.fail('로컬 STT 연결이 끊겼습니다. 확정된 초안은 유지됩니다.')
      socket.onmessage = event => {
        if (!current()) return
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'status' && message.stage === 'ready' && this.state.phase === 'starting') {
            source.connect(worklet); worklet.connect(context.destination)
            this.set({ phase: 'listening', device: message.device === 'cuda' ? 'GPU' : 'CPU' })
            // shortcut: bound each recording to two minutes; extend after long-session memory testing.
            clearTimeout(this.timer); this.timer = setTimeout(() => this.stop(), 120000)
          }
          const result = transcript.read(message)
          if (result.partial !== undefined) this.set({ partial: result.partial })
          if (result.final !== undefined) { if (result.final.trim()) this.commit(result.final); this.set({ partial: '' }) }
          if (result.done) { this.release(); this.set({ phase: 'off', partial: '' }) }
        } catch (error) { this.fail(error instanceof Error ? error.message : '음성 인식 결과를 읽을 수 없습니다.') }
      }
    } catch (error) {
      if (!current()) return
      this.fail(error instanceof DOMException && error.name === 'NotAllowedError' ? '마이크 권한이 거절됐습니다. 브라우저 사이트 설정에서 허용한 뒤 다시 켜 주세요.'
        : error instanceof DOMException && error.name === 'NotFoundError' ? '마이크를 찾지 못했습니다. 헤드셋 연결을 확인해 주세요.'
          : error instanceof Error ? error.message : '마이크를 시작하지 못했습니다.')
    }
  }
}
