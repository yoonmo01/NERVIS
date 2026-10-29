// Written for the deferred verification pass; no real speech or network is used.
import test from 'node:test'
import type { TestContext } from 'node:test'
import assert from 'node:assert/strict'
import { pcmSamples, speechText, SpeechPlayer, waveAudio } from '../src/tts.ts'

test('speech text removes display markup while preserving Korean and decimal values', () => {
  assert.equal(speechText('## 결과\n**상관계수**는 0.95입니다. [설명](https://example.com)\n```js\nsecret()\n```'), '결과 상관계수는 0.95입니다. 설명')
  assert.deepEqual(Array.from(pcmSamples(new Uint8Array([0, 128, 0, 0, 255, 127]).buffer)), [-1, 0, 32767 / 32768])
  assert.throws(() => pcmSamples(new ArrayBuffer(1)))
})

function browser(t: TestContext) {
  let closes = 0, stops = 0
  const sources: Source[] = []
  const contexts: Context[] = []
  const audios: MockAudio[] = []
  class MockAudio {
    onended: null | (() => void) = null
    onerror: null | (() => void) = null
    playbackRate = 1
    preservesPitch = false
    constructor(_url: string) { audios.push(this) }
    async play() {}
    pause() { stops++ }
    removeAttribute(_name: string) {}
    load() {}
  }
  let frame: (() => void) | undefined
  class Source {
    buffer: { duration: number } | null = null
    onended: null | (() => void) = null
    started = -1
    connect() {}
    disconnect() {}
    start(time: number) { this.started = time }
    stop() { stops++ }
  }
  class Context {
    constructor() { contexts.push(this) }
    currentTime = 0
    state = 'running'
    destination = {}
    async resume() {}
    async close() { closes++ }
    createAnalyser() { return { fftSize: 256, connect() {}, disconnect() {}, getFloatTimeDomainData(a: Float32Array) { a.fill(0) } } }
    createBuffer(_channels: number, size: number, rate: number) { const samples = new Float32Array(size); return { length: size, sampleRate: rate, duration: size / rate, getChannelData: () => samples } }
    createMediaElementSource(_audio: MockAudio) { const source = new Source(); sources.push(source); return source }
  }
  class Socket {
    static instances: Socket[] = []
    readyState = 1
    sent: string[] = []
    onopen: null | (() => void) = null
    onmessage: null | ((e: { data: string | ArrayBuffer }) => void) = null
    onerror: null | (() => void) = null
    onclose: null | (() => void) = null
    constructor(_url: string) { Socket.instances.push(this) }
    send(data: string) { this.sent.push(data) }
    close() { this.readyState = 3 }
    message(data: unknown) { this.onmessage?.({ data: data instanceof ArrayBuffer ? data : JSON.stringify(data) }) }
  }
  for (const [name, value] of Object.entries({ location: { protocol: 'http:', host: '127.0.0.1:5173' },
    Audio: MockAudio, AudioContext: Context, WebSocket: Socket, requestAnimationFrame: (tick: () => void): number => { frame = tick; return 1 }, cancelAnimationFrame: (): void => { frame = undefined } })) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, name)
    Object.defineProperty(globalThis, name, { value, configurable: true })
    t.after(() => { if (previous) Object.defineProperty(globalThis, name, previous); else Reflect.deleteProperty(globalThis, name) })
  }
  return { Socket, sources, contexts, audios, tick: () => frame?.(), counts: () => ({ closes, stops }) }
}

test('full text is requested once and no source starts until all PCM has arrived', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('첫 문장. 다음 문장.', [{ text: '첫 문장.', target: 'r0.weather' }, { text: '다음 문장.', target: 'r0.tasks' }])
  const socket = env.Socket.instances[0]
  socket.onopen?.()
  assert.deepEqual(JSON.parse(socket.sent[0]), { text: '첫 문장. 다음 문장.' })
  socket.message({ type: 'start', sample_rate: 24000, channels: 1, format: 'pcm16' })
  socket.message(new ArrayBuffer(9600))
  socket.message(new ArrayBuffer(9600))
  assert.equal(player.state.phase, 'preparing')
  assert.equal(env.sources.length, 0)
  socket.message({ type: 'done' })
  await Promise.resolve()
  assert.equal(player.state.phase, 'speaking')
  assert.equal(env.sources.length, 1)
  assert.equal(env.audios[0].playbackRate, 1.15)
  assert.equal(env.audios[0].preservesPitch, true)
  env.audios[0].onended?.()
  assert.equal(player.state.phase, 'idle')
  assert.deepEqual(JSON.parse(socket.sent[1]), { type: 'playback.finished' })
})

test('prepared audio waits for the screen gate and cancellation discards it', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('전체 응답.', [], undefined, true)
  const socket = env.Socket.instances[0]
  socket.message({ type: 'start', sample_rate: 24000, channels: 1, format: 'pcm16' })
  socket.message(new ArrayBuffer(9600))
  socket.message({ type: 'done' })
  assert.equal(player.state.phase, 'ready')
  assert.equal(env.sources.length, 0)
  player.stop()
  await player.start()
  assert.equal(env.sources.length, 0)
  assert.equal(player.state.phase, 'idle')
})

test('sending can prime autoplay without generating speech and the reply reuses that context', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.prepare()
  assert.equal(env.Socket.instances.length, 0)
  await player.play('자동 응답입니다.')
  assert.equal(env.counts().closes, 0)
  env.Socket.instances[0].onopen?.()
  assert.deepEqual(JSON.parse(env.Socket.instances[0].sent[0]), { text: '자동 응답입니다.' })
  player.stop()
  assert.equal(env.counts().closes, 1)
})

test('markup normalization mismatch falls back to ordinary narration without losing answer text', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('오늘 1. 발표', [{ text: '오늘', target: 'response' }, { text: '1. 발표', target: 'r0.tasks.0' }])
  const socket = env.Socket.instances[0]
  socket.onopen?.()
  assert.deepEqual(JSON.parse(socket.sent[0]), { text: '오늘 1. 발표' })
  assert.equal(player.state.synchronized, false)
  assert.equal(player.state.phase, 'preparing')
  player.stop()
})

test('stop cancels queued audio, closes transport, and ignores late PCM', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('응답입니다.')
  const socket = env.Socket.instances[0]
  socket.message({ type: 'start', sample_rate: 24000, channels: 1, format: 'pcm16' })
  socket.message(new ArrayBuffer(9600))
  player.stop()
  socket.message(new ArrayBuffer(9600))
  assert.equal(player.state.phase, 'idle')
  assert.equal(env.sources.length, 0)
  assert.deepEqual(env.counts(), { closes: 1, stops: 0 })
})

test('invalid metadata and network failure release the audio context without retry', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('응답입니다.')
  env.Socket.instances[0].message(new ArrayBuffer(2))
  assert.equal(player.state.phase, 'error')
  await player.play('응답입니다.')
  env.Socket.instances[1].onclose?.()
  assert.equal(player.state.phase, 'error')
  assert.equal(env.counts().closes, 2)
  await player.play('가'.repeat(2001))
  assert.equal(player.state.phase, 'error')
  assert.equal(env.Socket.instances.length, 2)
})

test('local WAV packaging preserves the original sample rate and PCM values', async () => {
  const buffer = { length: 3, sampleRate: 24000, getChannelData: () => new Float32Array([-1, 0, 1]) } as unknown as AudioBuffer
  const bytes = await waveAudio(buffer).arrayBuffer(), view = new DataView(bytes)
  assert.equal(new TextDecoder().decode(bytes.slice(0, 4)), 'RIFF')
  assert.equal(view.getUint32(24, true), 24000)
  assert.equal(view.getInt16(44, true), -32768)
  assert.equal(view.getInt16(48, true), 32767)
})
