import assert from 'node:assert/strict'
import test from 'node:test'
import { preferredSlice, pairedSlices, sliceCloud, advanceSample, signalStrength } from '../src/analysisModel.ts'
import { loadStage } from '../src/stageData.ts'
import { api, ApiError } from '../src/api.ts'

test('slice choice prioritizes visibility of both ROIs and has an absent-region fallback', () => {
  const records = [
    { orientation: 'Axial' as const, slice_index: 1, pixel_counts: { '1': 100, '11': 0 } },
    { orientation: 'Axial' as const, slice_index: 2, pixel_counts: { '1': 20, '11': 25 } },
    { orientation: 'Axial' as const, slice_index: 3, pixel_counts: { '1': 18, '11': 100 } },
  ]
  assert.equal(preferredSlice(records, 1, 11)?.slice_index, 2)
  assert.equal(preferredSlice(records.slice(0, 1), 1, 11)?.slice_index, 1)
  assert.equal(preferredSlice([], 1, 11), null)
  assert.deepEqual(records.map(r => r.slice_index), [1, 2, 3])
})

test('dual MRI chooses a useful slice in each orientation without dropping the weaker direction', () => {
  const records = [
    { orientation: 'Axial' as const, slice_index: 91, pixel_counts: { '6': 400, '16': 500 } },
    { orientation: 'Coronal' as const, slice_index: 161, pixel_counts: { '6': 20, '16': 30 } },
    { orientation: 'Coronal' as const, slice_index: 171, pixel_counts: { '6': 1, '16': 200 } },
  ]
  assert.deepEqual(pairedSlices(records, 6, 16).map(r => [r.orientation, r.slice_index]), [['Axial', 91], ['Coronal', 161]])
  assert.deepEqual(records.map(r => r.slice_index), [91, 161, 171])
  assert.throws(() => pairedSlices(records.slice(0, 1), 6, 16), /Coronal/)
})

test('spatial points preserve image left/right and mask IDs; bounds use all pixels', () => {
  const t1 = new Uint8ClampedArray([100, 100, 100, 255, 200, 200, 200, 255, 0, 0, 0, 255, 90, 90, 90, 255])
  const mask = new Uint8ClampedArray([1, 1, 1, 255, 11, 11, 11, 255, 0, 0, 0, 255, 11, 11, 11, 255])
  const before = [...mask]
  const cloud = sliceCloud(t1, mask, 2, 2, 1, 11, 1)
  assert.deepEqual([...cloud.regionA], [-2, 2, 0])
  assert.deepEqual([...cloud.regionB], [2, 2, 0, 2, -2, 0])
  assert.equal(cloud.tissue.length, 9)
  assert.deepEqual(cloud.boundsB, { x: 1, y: 0, width: 1, height: 2 })
  assert.deepEqual(cloud.centerB, [2, 0, 0])
  assert.deepEqual([...mask], before)
  assert.equal(sliceCloud(t1, mask, 2, 2, 2, 12, 1).boundsA, null)
  assert.throws(() => sliceCloud(t1, mask.slice(4), 2, 2, 1, 11, 1))
})

test('sample playback loops inside inclusive selected bounds, never treating samples as seconds', () => {
  assert.equal(advanceSample(200, 1, 200), 1)
  assert.equal(advanceSample(15, 10, 20, 10), 14)
  assert.equal(advanceSample(1, 50, 99), 50)
  assert.equal(advanceSample(50, 50, 50), 50)
  assert.throws(() => advanceSample(1, 20, 10))
  assert.equal(signalStrength(Number.NaN), 0)
  assert.equal(signalStrength(0), 0)
  assert.equal(signalStrength(-1.5), 0.5)
  assert.equal(signalStrength(100), 1)
})

test('stage loading rejects HTTP failures and mixed data versions before image processing', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response('{}', { status: 503 })
    await assert.rejects(loadStage([], 'expected', null, new AbortController().signal, () => {}), /503/)
    globalThis.fetch = async () => new Response(JSON.stringify({ dataset_version: 'other', pairs: [] }), { status: 200 })
    await assert.rejects(loadStage([], 'expected', null, new AbortController().signal, () => {}), /버전/)
  } finally { globalThis.fetch = original }
})

test('explicit pair, subrange and method reach every local calculation without an automatic search', async () => {
  const original = globalThis.fetch, requests: { path: string; body: unknown }[] = []
  try {
    globalThis.fetch = async (path, options) => {
      requests.push({ path: String(path), body: options?.body ? JSON.parse(String(options.body)) : null })
      return new Response(JSON.stringify({ dataset_version: 'other' }))
    }
    await assert.rejects(loadStage([], 'expected', { region: 2, region_b: 3, start: 51, end: 150, method: 'spearman', window: 40, step: 5 }, new AbortController().signal, () => {}), /버전/)
    assert.deepEqual(requests.slice(0, 2), [
      { path: '/api/analysis/compare', body: { region_a: 2, region_b: 3, start: 51, end: 150, method: 'spearman' } },
      { path: '/api/analysis/windows', body: { region_a: 2, region_b: 3, start: 51, end: 150, method: 'spearman', window: 40, step: 5 } },
    ])
    assert.equal(requests.length, 4)
    globalThis.fetch = async () => new Response('null', { status: 502 })
    await assert.rejects(api('/api/ai/chat', new AbortController().signal, { command: 'test' }), error => error instanceof ApiError && error.code === 'request_failed')
  } finally { globalThis.fetch = original }
})
