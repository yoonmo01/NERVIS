import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { cameraPresets, cameraPoseBetween, sampleSurfacePoints, validBrainLayout } from './hologramModel.ts'

test('brain layout accepts only twenty unique mapped regions and four unlabelled context meshes', () => {
  const regions = Array.from({ length: 20 }, (_, i) => ({ label_id: i + 1, glb_nodes: ['ROI_' + (i + 1)] }))
  const context = ['Cortex_Shell_L', 'Cortex_Shell_R', 'Cerebellum_Context', 'Brainstem_Context'].map(name => ({ name }))
  const nodes = [...context, ...regions.map(r => ({ name: r.glb_nodes[0], id: r.label_id }))]
  assert.equal(validBrainLayout(nodes, regions), true)
  assert.equal(validBrainLayout(nodes.slice(1), regions), false)
  assert.equal(validBrainLayout([...nodes, { name: 'unknown' }], regions), false)
  assert.equal(validBrainLayout(nodes.map((n, i) => i === 2 ? { ...n, id: 21 } : n), regions), false)
  assert.equal(validBrainLayout(nodes.map((n, i) => i === 4 ? nodes[5] : n), regions), false)
  assert.equal(validBrainLayout(nodes.map((n, i) => i === 4 ? { ...n, id: 11 } : n), regions), false)
  assert.equal(validBrainLayout(nodes.map((n, i) => i === 2 ? { name: 'unknown' } : n), regions), false)
})

test('internal oblique is the first preset and the former default preset is removed', () => {
  assert.equal(Object.keys(cameraPresets)[0], 'oblique')
  assert.equal('default' in cameraPresets, false)
  assert.deepEqual(cameraPresets.oblique.position, [5.2, 4.2, 4.4])
  assert.equal(cameraPresets.oblique.label, '기본')
})

test('camera presets retain anatomical axes and opposite views move around the brain', () => {
  assert.ok(cameraPresets.front.position[2] > 0)
  assert.ok(cameraPresets.back.position[2] < 0)
  assert.ok(cameraPresets.left.position[0] > 0)
  assert.ok(cameraPresets.right.position[0] < 0)
  assert.deepEqual(cameraPresets.top.up, [0, 0, -1])
  const from = [0, 0, 8], to = [0, 0, -8]
  assert.deepEqual(cameraPoseBetween(from, to, 0).position.toArray(), from)
  assert.ok(cameraPoseBetween(from, to, 1).position.distanceTo(cameraPoseBetween(to, from, 0).position) < 1e-10)
  for (let i = 0; i <= 10; i++) {
    const { position, up } = cameraPoseBetween(from, to, i / 10)
    assert.ok(Math.abs(position.clone().normalize().dot(up)) < 1e-10)
    assert.ok(position.toArray().every(Number.isFinite))
    assert.ok(Math.abs(position.length() - 8) < 1e-10)
  }
  for (const a of Object.values(cameraPresets)) for (const b of Object.values(cameraPresets)) for (const t of [0, .25, .5, .75, 1]) {
    const pose = cameraPoseBetween(a.position, b.position, t, a.up, b.up)
    assert.ok(pose.position.toArray().concat(pose.up.toArray()).every(Number.isFinite))
    assert.ok(pose.position.length() >= 7.99)
    const source = cameraPoseBetween(a.position, a.position, 0, a.up, a.up).position.normalize()
    const target = cameraPoseBetween(b.position, b.position, 0, b.up, b.up).position.normalize()
    const angularDistance = Math.acos(Math.max(-1, Math.min(1, source.dot(target))))
    const travelled = Math.acos(Math.max(-1, Math.min(1, source.dot(pose.position.clone().normalize()))))
    assert.ok(Math.abs(travelled - angularDistance * t) < 1e-7, 'camera takes the shortest positional arc independently of screen roll')
    assert.ok(Math.abs(pose.position.clone().normalize().dot(pose.up)) < 1e-10)
    if (t === 1) assert.ok(pose.position.distanceTo(cameraPoseBetween(b.position, b.position, 0, b.up, b.up).position) < 1e-10)
  }
  assert.throws(() => cameraPoseBetween([0, 0, 0], to, .5))
})

test('surface particles are deterministic, bounded and do not change model vertices', () => {
  const positions = new Float32Array([1, 2, 3, -1, -2, -3, 0, 1, 0])
  const before = positions.slice()
  const points = sampleSurfacePoints(positions, 100)
  assert.deepEqual(points, sampleSurfacePoints(positions, 100))
  assert.equal(points.length, 300)
  for (let i = 0; i < points.length; i += 3) assert.ok([[1, 2, 3], [-1, -2, -3], [0, 1, 0]].some(p => p.every((n, j) => n === points[i + j])))
  assert.deepEqual(positions, before)
  assert.throws(() => sampleSurfacePoints(new Float32Array(), 1))
  assert.throws(() => sampleSurfacePoints(positions, -1))
  assert.throws(() => sampleSurfacePoints(new Float32Array([NaN, 0, 0]), 1))
})

test('hologram delivery has independent 20 ROI nodes and four bounded surface attributes', () => {
  const buffer = readFileSync(new URL('./assets/nervis-hologram-brain-narrow-gap.glb', import.meta.url))
  assert.equal(buffer.readUInt32LE(0), 0x46546c67)
  assert.equal(buffer.readUInt32LE(8), buffer.length)
  const doc = JSON.parse(buffer.subarray(20, 20 + buffer.readUInt32LE(12)).toString())
  const binaryStart = 28 + buffer.readUInt32LE(12)
  assert.equal(doc.meshes.length, 24)
  const map = JSON.parse(readFileSync(new URL('./assets/hologram-region-map-narrow-gap.json', import.meta.url)).toString())
  assert.equal(validBrainLayout(doc.nodes.filter((n: { mesh?: number }) => n.mesh !== undefined).map((n: { name: string; extras?: { label_id?: number } }) => ({ name: n.name, id: n.extras?.label_id })), map.regions), true)
  assert.equal(doc.images?.length ?? 0, 0)
  assert.ok(doc.buffers.every((b: { uri?: string }) => !b.uri))
  const ids = doc.nodes.filter((n: { extras?: { label_id?: number } }) => n.extras?.label_id).map((n: { extras: { label_id: number } }) => n.extras.label_id)
  assert.deepEqual(ids.sort((a: number, b: number) => a - b), Array.from({ length: 20 }, (_, i) => i + 1))
  for (const mesh of doc.meshes) for (const primitive of mesh.primitives) {
    for (const name of ['_NERVIS_RIDGE', '_NERVIS_EDGE', '_NERVIS_CONTEXT', '_NERVIS_MICRO']) {
      const accessor = doc.accessors[primitive.attributes[name]]
      assert.ok(accessor && accessor.count === doc.accessors[primitive.attributes.POSITION].count, name)
      assert.equal(accessor.componentType, 5126)
      const view = doc.bufferViews[accessor.bufferView]
      const offset = binaryStart + (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0)
      for (let i = 0; i < accessor.count; i++) {
        const value = buffer.readFloatLE(offset + i * (view.byteStride ?? 4))
        assert.ok(Number.isFinite(value) && value >= 0 && value <= 1, name)
      }
    }
  }
})
