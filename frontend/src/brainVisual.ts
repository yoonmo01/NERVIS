import type { Region } from './api.ts'

export function displayColor(region: Region): number[] {
  return region.hemisphere === 'Left' ? [41, 223, 212] : [255, 191, 99]
}

export function hemispherePair(regions: Region[], selected: number): [Region, Region] {
  const a = regions.find(region => region.label_id === selected)
  const b = regions.find(region => region.label_id === a?.contralateral_id)
  if (!a || !b || b.contralateral_id !== a.label_id || a.hemisphere === b.hemisphere) throw new Error('좌우 대응 영역을 확인할 수 없습니다.')
  return a.hemisphere === 'Left' ? [a, b] : [b, a]
}

export function maskBoundary(mask: Uint8ClampedArray, width: number, height: number, id: number, color: number[]) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || mask.length !== width * height * 4) throw new Error('마스크 크기가 일치하지 않습니다.')
  const edge = new Uint8ClampedArray(mask.length)
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const p = y * width + x, at = p * 4
    if (mask[at] !== id) continue
    if (x === 0 || y === 0 || x === width - 1 || y === height - 1 || [p - 1, p + 1, p - width, p + width].some(n => mask[n * 4] !== id)) {
      edge.set([color[0], color[1], color[2], 255], at)
    }
  }
  return edge
}
