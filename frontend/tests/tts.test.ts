// Written for the deferred verification pass; no real speech or network is used.
import test from 'node:test'
import type { TestContext } from 'node:test'
import assert from 'node:assert/strict'
import { pcmSamples, speechText, SpeechPlayer } from '../src/tts.ts'

test('speech text removes display markup while preserving Korean and decimal values', () => {
  assert.equal(speechText('## 결과\n**상관계수**는 0.95입니다. [설명](https://example.com)\n```js\nsecret()\n```'), '결과 상관계수는 0.95입니다. 설명')
  assert.deepEqual(Array.from(pcmSamples(new Uint8Array([0, 128, 0, 0, 255, 127]).buffer)), [-1, 0, 32767 / 32768])
  assert.throws(() => pcmSamples(new ArrayBuffer(1)))
})

function browser(t: TestContext) {
  let closes = 0, stops = 0
  const sources: Source[] = []
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
    currentTime = 0
    state = 'running'
    destination = {}
    async resume() {}
    async close() { closes++ }
    createAnalyser() { return { fftSize: 256, connect() {}, disconnect() {}, getFloatTimeDomainData(a: Float32Array) { a.fill(0) } } }
    createBuffer(_channels: number, size: number, rate: number) { return { duration: size / rate, getChannelData: () => new Float32Array(size) } }
    createBufferSource() { const source = new Source(); sources.push(source); return source }
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
    AudioContext: Context, WebSocket: Socket, requestAnimationFrame: (): number => 1, cancelAnimationFrame: (): void => {} })) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, name)
    Object.defineProperty(globalThis, name, { value, configurable: true })
    t.after(() => { if (previous) Object.defineProperty(globalThis, name, previous); else Reflect.deleteProperty(globalThis, name) })
  }
  return { Socket, sources, counts: () => ({ closes, stops }) }
}

test('first PCM starts before generation finishes; chunks retain order and unlock after playback', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('첫 문장. 다음 문장.', 'JARVIS')
  const socket = env.Socket.instances[0]
  socket.onopen?.()
  assert.deepEqual(JSON.parse(socket.sent[0]), { text: '첫 문장. 다음 문장.', voice: 'JARVIS' })
  socket.message({ type: 'start', sample_rate: 24000, channels: 1, format: 'pcm16' })
  socket.message(new ArrayBuffer(9600))
  assert.equal(player.state.phase, 'speaking')
  assert.equal(env.sources[0].started, .06)
  socket.message(new ArrayBuffer(9600))
  assert.equal(env.sources[1].started, .26)
  socket.message({ type: 'done' })
  assert.equal(player.state.phase, 'speaking')
  env.sources[0].onended?.()
  assert.equal(player.state.phase, 'speaking')
  env.sources[1].onended?.()
  assert.equal(player.state.phase, 'idle')
  assert.equal(socket.readyState, 3)
  assert.deepEqual(JSON.parse(socket.sent[1]), { type: 'playback.finished' })
  assert.equal(env.counts().closes, 1)
})

test('stop cancels queued audio, closes transport, and ignores late PCM', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('응답입니다.', 'JARVIS_2')
  const socket = env.Socket.instances[0]
  socket.message({ type: 'start', sample_rate: 24000, channels: 1, format: 'pcm16' })
  socket.message(new ArrayBuffer(9600))
  player.stop()
  socket.message(new ArrayBuffer(9600))
  assert.equal(player.state.phase, 'idle')
  assert.equal(env.sources.length, 1)
  assert.deepEqual(env.counts(), { closes: 1, stops: 1 })
})

test('invalid metadata and network failure release the audio context without retry', async t => {
  const env = browser(t), player = new SpeechPlayer(() => {})
  await player.play('응답입니다.', 'JARVIS')
  env.Socket.instances[0].message(new ArrayBuffer(2))
  assert.equal(player.state.phase, 'error')
  await player.play('응답입니다.', 'JARVIS')
  env.Socket.instances[1].onclose?.()
  assert.equal(player.state.phase, 'error')
  assert.equal(env.counts().closes, 2)
  await player.play('가'.repeat(2001), 'JARVIS')
  assert.equal(player.state.phase, 'error')
  assert.equal(env.Socket.instances.length, 2)
})
