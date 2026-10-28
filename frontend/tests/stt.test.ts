import test from 'node:test'
import type { TestContext } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { appendTranscript, Transcript, Dictation } from '../src/stt.ts'

test('confirmed speech appends to the latest edited draft without truncation', () => {
  assert.equal(appendTranscript('기존 초안 수정', '오늘 수업 알려줘'), '기존 초안 수정 오늘 수업 알려줘')
  assert.equal(appendTranscript('초안\n', '확정'), '초안\n확정')
  assert.equal(appendTranscript('a'.repeat(599), '말'), null)
  assert.equal(appendTranscript('', '가'.repeat(600)), '가'.repeat(600))
})

test('partials never commit and summary only commits the tail after utterances', () => {
  const transcript = new Transcript()
  assert.deepEqual(transcript.read({ type: 'partial', text: '오늘' }), { partial: '오늘' })
  assert.deepEqual(transcript.read({ type: 'final', final_kind: 'utterance', text: '오늘 수업.' }), { final: '오늘 수업.' })
  assert.deepEqual(transcript.read({ type: 'final', final_kind: 'summary', text: '오늘 수업.할 일.',
    segments: [{ text: '오늘 수업.' }, { text: '할 일.' }] }), { final: '할 일.', done: true })
})

test('summary does not reinsert edited utterances; malformed and server errors fail closed', () => {
  const transcript = new Transcript()
  transcript.read({ type: 'final', final_kind: 'utterance', text: '첫 문장.' })
  assert.deepEqual(transcript.read({ type: 'final', final_kind: 'summary', text: '첫 문장.', segments: [{ text: '첫 문장.' }] }), { final: '', done: true })
  assert.throws(() => transcript.read({ type: 'final', text: 123 }))
  assert.throws(() => transcript.read({ type: 'error', message: 'internal path and secret' }), /로컬 STT/)
  assert.throws(() => transcript.read({ type: 'final', final_kind: 'summary', text: '첫 문장.' }))
})

function browser(t: TestContext) {
  let trackStops = 0, contextCloses = 0, mediaCalls = 0
  const track = { stop: () => { trackStops++ }, onended: null as null | (() => void) }
  const stream = { getTracks: () => [track] }
  const source = { connect() {}, disconnect() {} }
  class Context {
    sampleRate = 16000
    destination = {}
    audioWorklet = { addModule: async () => {} }
    createMediaStreamSource() { return source }
    async resume() {}
    async close() { contextCloses++ }
  }
  class Worklet {
    port = { onmessage: null as null | ((e: { data: ArrayBuffer }) => void), close() {} }
    connect() {}
    disconnect() {}
  }
  class Socket {
    static instances: Socket[] = []
    readyState = 1
    bufferedAmount = 0
    sent: unknown[] = []
    onopen: null | (() => void) = null
    onmessage: null | ((e: { data: string }) => void) = null
    onerror: null | (() => void) = null
    onclose: null | (() => void) = null
    constructor(_url: string) { Socket.instances.push(this) }
    send(data: unknown) { this.sent.push(data) }
    close() { this.readyState = 3 }
    message(value: unknown) { this.onmessage?.({ data: JSON.stringify(value) }) }
  }
  for (const [key, value] of Object.entries({ navigator: { mediaDevices: { getUserMedia: async () => { mediaCalls++; return stream } } },
    location: { protocol: 'http:', host: '127.0.0.1:5173' }, AudioContext: Context, AudioWorkletNode: Worklet, WebSocket: Socket })) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, key)
    Object.defineProperty(globalThis, key, { configurable: true, value })
    t.after(() => { if (previous) Object.defineProperty(globalThis, key, previous); else Reflect.deleteProperty(globalThis, key) })
  }
  t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => ({ ready: true, language: 'ko', busy: false }) }))
  return { Socket, track, counts: () => ({ trackStops, contextCloses, mediaCalls }) }
}

test('stop releases microphone immediately, waits for final, and closes transport', async t => {
  const env = browser(t), final: string[] = []
  const session = new Dictation(() => {}, text => final.push(text))
  await session.start('/worklet.js')
  const socket = env.Socket.instances[0]
  socket.message({ type: 'status', stage: 'ready' })
  assert.equal(session.state.phase, 'listening')
  session.stop()
  assert.equal(env.counts().trackStops, 1)
  assert.equal(env.counts().contextCloses, 1)
  assert.deepEqual(socket.sent, [JSON.stringify({ type: 'input_audio.end' })])
  assert.equal(session.state.phase, 'stopping')
  socket.message({ type: 'final', final_kind: 'summary', text: '안녕하세요.', segments: [{ text: '안녕하세요.' }] })
  assert.deepEqual(final, ['안녕하세요.'])
  assert.equal(session.state.phase, 'off')
  assert.equal(socket.readyState, 3)
})

test('permission rejection, network loss, and cancellation leave no active microphone', async t => {
  const env = browser(t)
  const session = new Dictation(() => {}, () => assert.fail('cancelled speech must not commit'))
  t.mock.method(navigator.mediaDevices, 'getUserMedia', async () => { throw new DOMException('denied', 'NotAllowedError') })
  await session.start('/worklet.js')
  assert.equal(session.state.phase, 'error')
  assert.match(session.state.error, /권한/)
  t.mock.method(navigator.mediaDevices, 'getUserMedia', async () => ({ getTracks: () => [env.track] }))
  await session.start('/worklet.js')
  env.Socket.instances[0].onclose?.()
  assert.equal(session.state.phase, 'error')
  assert.equal(env.counts().trackStops, 1)
  await session.start('/worklet.js')
  session.cancel()
  env.Socket.instances[1].message({ type: 'final', text: '늦은 응답' })
  assert.equal(env.counts().trackStops, 2)
  assert.equal(session.state.phase, 'off')
})

test('cancelling a pending permission releases late tracks and never opens a socket', async t => {
  const env = browser(t)
  let grant!: (s: unknown) => void
  t.mock.method(navigator.mediaDevices, 'getUserMedia', () => new Promise(resolve => { grant = resolve }))
  const session = new Dictation(() => {}, () => {})
  const pending = session.start('/worklet.js')
  while (!grant) await new Promise(resolve => setImmediate(resolve))
  session.cancel()
  grant({ getTracks: () => [env.track] })
  await pending
  assert.equal(env.counts().trackStops, 1)
  assert.equal(env.Socket.instances.length, 0)
})

test('missing local Korean model or busy service blocks microphone capture', async t => {
  const env = browser(t)
  for (const status of [{ ready: false, language: 'ko' }, { ready: true, language: 'auto' }, { ready: true, language: 'ko', busy: true }]) {
    t.mock.method(globalThis, 'fetch', async () => ({ ok: true, json: async () => status }))
    const session = new Dictation(() => {}, () => {})
    await session.start('/worklet.js')
    assert.equal(session.state.phase, 'error')
  }
  assert.equal(env.counts().mediaCalls, 0)
})

test('server and final timeouts close tracks and transport without losing confirmed text', async t => {
  const env = browser(t)
  t.mock.timers.enable({ apis: ['setTimeout'] })
  const session = new Dictation(() => {}, () => {})
  await session.start('/worklet.js')
  t.mock.timers.tick(70001)
  assert.equal(session.state.phase, 'error')
  assert.equal(env.counts().trackStops, 1)
  assert.equal(env.Socket.instances[0].readyState, 3)
  await session.start('/worklet.js')
  env.Socket.instances[1].message({ type: 'status', stage: 'ready', device: 'cuda' })
  assert.equal(session.state.device, 'GPU')
  session.stop()
  t.mock.timers.tick(60001)
  assert.equal(session.state.phase, 'error')
  assert.equal(env.counts().trackStops, 2)
  assert.equal(env.Socket.instances[1].readyState, 3)
})

test('microphone worklet emits bounded signed PCM without monitoring audio', () => {
  let Processor: any
  const frames: ArrayBuffer[] = []
  runInNewContext(readFileSync(new URL('../src/microphone-worklet.js', import.meta.url), 'utf8'), {
    AudioWorkletProcessor: class { port = { postMessage: (data: ArrayBuffer) => frames.push(data) } },
    registerProcessor: (_name: string, implementation: unknown) => { Processor = implementation },
  })
  const worklet = new Processor()
  assert.equal(worklet.process([[new Float32Array([-2, -1, 0, .5, 1, 2])]]), true)
  assert.deepEqual(Array.from(new Int16Array(frames[0])), [-32768, -32768, 0, 16384, 32767, 32767])
  assert.equal(worklet.process([]), true)
  assert.equal(frames.length, 1)
})
