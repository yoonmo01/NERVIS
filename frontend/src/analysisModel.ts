import type { Slice } from './api.ts'

export function preferredSlice(records: Slice[], a: number, b: number): Slice | null {
  let best: Slice | null = null, score = -1
  for (const record of records) {
    const x = record.pixel_counts[String(a)] ?? 0, y = record.pixel_counts[String(b)] ?? 0
    const next = Math.min(x, y) * 1e7 + x + y
    if (next > score) { best = record; score = next }
  }
  return best
}

export function pairedSlices(records: Slice[], a: number, b: number): Slice[] {
  return (['Axial', 'Coronal'] as const).map(orientation => {
    const record = preferredSlice(records.filter(item => item.orientation === orientation), a, b)
    if (!record) throw new Error(`${orientation} 제공 단면을 찾을 수 없습니다.`)
    return record
  })
}

export interface Bounds { x: number; y: number; width: number; height: number }
export function sliceCloud(t1: Uint8ClampedArray, mask: Uint8ClampedArray, width: number, height: number,
  a: number, b: number, stride = 6) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 2 || height < 2 ||
    !Number.isInteger(stride) || stride < 1 || t1.length !== width * height * 4 || mask.length !== t1.length) throw new Error('Invalid slice pixels')
  const tissue: number[] = [], colors: number[] = [], points: number[][] = [[], []]
  const extents = [[width, height, -1, -1], [width, height, -1, -1]]
  const sums = [[0, 0, 0], [0, 0, 0]]
  const position = (x: number, y: number) => [(x / (width - 1) - .5) * 4 * width / height, (.5 - y / (height - 1)) * 4, 0]
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const offset = (y * width + x) * 4, id = mask[offset], gray = t1[offset] / 255
    const group = id === a ? 0 : id === b ? 1 : -1
    if (group >= 0) {
      const extent = extents[group], sum = sums[group]
      extent[0] = Math.min(extent[0], x); extent[1] = Math.min(extent[1], y)
      extent[2] = Math.max(extent[2], x); extent[3] = Math.max(extent[3], y)
      sum[0] += x; sum[1] += y; sum[2]++
    }
    if (x % stride || y % stride || (gray < .13 && group < 0)) continue
    const p = position(x, y)
    tissue.push(...p); colors.push(.12 + gray * .3, .32 + gray * .5, .5 + gray * .5)
    if (group >= 0) points[group].push(...p)
  }
  const bounds = (i: number): Bounds | null => sums[i][2] ? { x: extents[i][0], y: extents[i][1], width: extents[i][2] - extents[i][0] + 1, height: extents[i][3] - extents[i][1] + 1 } : null
  const center = (i: number) => sums[i][2] ? position(sums[i][0] / sums[i][2], sums[i][1] / sums[i][2]) : null
  return { tissue: new Float32Array(tissue), colors: new Float32Array(colors), regionA: new Float32Array(points[0]), regionB: new Float32Array(points[1]), boundsA: bounds(0), boundsB: bounds(1), centerA: center(0), centerB: center(1) }
}

export function advanceSample(sample: number, start: number, end: number, steps = 1) {
  if (![sample, start, end, steps].every(Number.isInteger) || start < 1 || end < start || steps < 0) throw new Error('Invalid playback range')
  if (sample < start || sample > end) return start
  return start + (sample - start + steps) % (end - start + 1)
}

export function signalStrength(value: number) { return Number.isFinite(value) ? Math.min(1, Math.abs(value) / 3) : 0 }
