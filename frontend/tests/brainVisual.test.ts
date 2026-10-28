import assert from 'node:assert/strict'
import test from 'node:test'
import { displayColor, hemispherePair, maskBoundary } from '../src/brainVisual.ts'
import type { Region } from '../src/api.ts'
import { readFileSync } from 'node:fs'

const left = { label_id: 1, contralateral_id: 11, hemisphere: 'Left', color_rgb: [1, 2, 3] } as Region
const right = { label_id: 11, contralateral_id: 1, hemisphere: 'Right', color_rgb: [4, 5, 6] } as Region
test('right-side selection keeps the left panel left without altering source colors', () => {
  assert.deepEqual(hemispherePair([right, left], 11), [left, right])
  assert.deepEqual(displayColor(left), [41, 223, 212])
  assert.deepEqual(displayColor(right), [255, 191, 99])
  assert.deepEqual(left.color_rgb, [1, 2, 3])
  assert.throws(() => hemispherePair([left], 1))
  assert.throws(() => hemispherePair([left, { ...right, contralateral_id: 2 }], 11))
})
test('mask boundary stays inside the exact selected pixels and retains holes', () => {
  const mask = new Uint8ClampedArray(5 * 5 * 4)
  for (let p = 0; p < 25; p++) mask[p * 4] = p === 12 ? 0 : 1
  const before = mask.slice()
  const edge = maskBoundary(mask, 5, 5, 1, [41, 223, 212])
  assert.equal(edge[3], 255)
  assert.equal(edge[12 * 4 + 3], 0)
  assert.equal(edge[7 * 4 + 3], 255)
  assert.equal(edge[6 * 4 + 3], 0)
  assert.deepEqual(mask, before)
  assert.throws(() => maskBoundary(mask, 4, 5, 1, [1, 2, 3]))
})

test('CC0 cortical model contains 20 side-correct regions and no images or external buffers', () => {
  const buffer = readFileSync(new URL('../src/assets/nervis-cortical-brain.glb', import.meta.url))
  assert.equal(buffer.readUInt32LE(0), 0x46546c67)
  assert.equal(buffer.readUInt32LE(4), 2)
  assert.equal(buffer.readUInt32LE(8), buffer.length)
  const doc = JSON.parse(buffer.subarray(20, 20 + buffer.readUInt32LE(12)).toString())
  assert.equal(doc.meshes.length, 22)
  assert.equal(doc.images?.length ?? 0, 0)
  assert.equal(doc.cameras?.length ?? 0, 0)
  assert.ok(doc.buffers.every((b: { uri?: string }) => !b.uri))
  const regions = doc.nodes.filter((n: { extras?: { label_id?: number } }) => n.extras?.label_id)
  assert.deepEqual(regions.map((n: { extras: { label_id: number } }) => n.extras.label_id).sort((a: number, b: number) => a - b), Array.from({ length: 20 }, (_, i) => i + 1))
  for (const node of regions) {
    const left = node.extras.label_id <= 10
    assert.equal(node.extras.hemisphere, left ? 'left' : 'right')
    assert.equal(node.extras.mapping_status, 'AUTHORED_ANATOMICAL_PROXY_NOT_ATLAS')
    for (const primitive of doc.meshes[node.mesh].primitives) {
      const accessor = doc.accessors[primitive.attributes.POSITION]
      assert.ok([...accessor.min, ...accessor.max].every(Number.isFinite))
      assert.ok(left ? accessor.min[0] > 0 : accessor.max[0] < 0)
    }
  }
})
