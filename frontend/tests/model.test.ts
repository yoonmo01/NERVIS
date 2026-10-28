import assert from 'node:assert/strict'
import test from 'node:test'
import * as model from '../src/model.ts'
import { introStage, makeCoreGeometry, maskOverlay, wavePath, audioLevel } from '../src/model.ts'

test('intro keeps title, docks it, reveals core, then enables controls', () => {
  assert.equal(introStage(0), 'title')
  assert.equal(introStage(1199), 'title')
  assert.equal(introStage(1200), 'dock')
  assert.equal(introStage(2600), 'core')
  assert.equal(introStage(4300), 'ready')
  assert.equal(introStage(0, true), 'ready')
})

test('layered geometry is deterministic, finite and bounded', () => {
  const a = makeCoreGeometry()
  const b = makeCoreGeometry()
  for (const key of ['shell', 'inner', 'particles'] as const) {
    assert.deepEqual(a[key], b[key])
    assert.ok(a[key].length > 100)
    assert.equal(a[key].length % 3, 0)
    assert.ok(a[key].every(v => Number.isFinite(v) && Math.abs(v) < 2.5))
  }
  assert.equal(a.shell.length % 6, 0)
})

test('home core adds detail within the same bounds while compact remains the default', () => {
  const compact = makeCoreGeometry(), home = makeCoreGeometry(true)
  assert.deepEqual(compact, makeCoreGeometry(false))
  assert.deepEqual(home, makeCoreGeometry(true))
  for (const key of ['shell', 'inner', 'panels', 'particles'] as const) {
    assert.ok(home[key].length > compact[key].length)
    assert.equal(home[key].length % 3, 0)
    assert.ok(home[key].every(v => Number.isFinite(v) && Math.abs(v) < 2.5))
  }
  assert.deepEqual(home.glow, compact.glow)
})

test('ID masks color only selected labels and preserve unlabelled pixels', () => {
  const pixels = new Uint8ClampedArray([0, 0, 0, 255, 1, 1, 1, 255, 11, 11, 11, 255, 2, 2, 2, 255])
  const output = maskOverlay(pixels, new Map([[1, [230, 70, 70]], [11, [150, 46, 46]]]))
  assert.deepEqual([...output], [0, 0, 0, 0, 230, 70, 70, 145, 150, 46, 46, 145, 0, 0, 0, 0])
  assert.equal(pixels[7], 255)
  assert.throws(() => maskOverlay(new Uint8ClampedArray(3), new Map()))
})

test('waveforms are finite SVG paths and invalid signal values are rejected', () => {
  assert.match(wavePath([0, 1, -1]), /^M/)
  assert.ok(!wavePath([0, 10, -10]).includes('NaN'))
  assert.equal(wavePath([]), '')
  assert.throws(() => wavePath([0, Number.NaN]))
})

test('audio preview level is zero for silence, bounded and responds to samples', () => {
  assert.equal(audioLevel(new Float32Array(8)), 0)
  assert.equal(audioLevel(new Float32Array()), 0)
  assert.ok(audioLevel(new Float32Array([0.1, -0.1])) > 0)
  assert.equal(audioLevel(new Float32Array([1, -1])), 1)
})

test('paired waveforms share one z-score scale', () => {
  assert.equal(wavePath([4], 4), 'M0.00,8.00')
  assert.equal(wavePath([2], 4), 'M0.00,34.00')
  assert.throws(() => wavePath([0], 0))
})

test('core panels are finite triangles and the glow fades to transparent edges', () => {
  const core = makeCoreGeometry()
  assert.ok(core.panels instanceof Float32Array)
  assert.ok(core.panels.length > 1000)
  assert.equal(core.panels.length % 9, 0)
  assert.ok(core.panels.every(v => Number.isFinite(v) && Math.abs(v) < 2.5))
  assert.equal(core.glow.length, 64 * 64 * 4)
  assert.equal(core.glow[3], 0)
  assert.ok(core.glow[(32 * 64 + 32) * 4 + 3] > 240)
})

test('core motion rotates faster, reacts to audio, and respects reduced motion', () => {
  const idle = model.coreMotion(0, 0, false)
  const moving = model.coreMotion(1, 0, false)
  assert.ok(moving.shellY - idle.shellY >= 0.16)
  assert.ok(moving.innerY < idle.innerY)
  const speaking = model.coreMotion(0, 1, false)
  assert.ok(speaking.scale > idle.scale && speaking.glow > idle.glow)
  assert.deepEqual(model.coreMotion(0, 0, true), model.coreMotion(100, 1, true))
  assert.deepEqual(model.coreMotion(0, 100, false), speaking)
  assert.ok(Object.values(model.coreMotion(Number.NaN, Number.NaN, false)).every(Number.isFinite))
  assert.equal(model.coreStateColors.error, '#ff626e')
  assert.notEqual(model.coreStateColors.processing, model.coreStateColors.analyzing)
  assert.deepEqual(model.coreMotion(0, 0, true, 'error'), model.coreMotion(100, 1, true, 'error'))
})

test('composer stays expanded at home and toggles closed in analysis', () => {
  assert.equal(model.toggleComposer('text', 'text', 'home'), 'text')
  assert.equal(model.toggleComposer('voice', 'voice', 'home'), 'text')
  assert.equal(model.toggleComposer('text', 'text', 'analysis'), null)
  assert.equal(model.toggleComposer(null, 'text', 'analysis'), 'text')
  assert.equal(model.toggleComposer('text', 'voice', 'analysis'), 'voice')
})
