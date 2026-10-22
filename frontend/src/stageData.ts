import { hemispherePair } from './brainVisual.ts'
import { api } from './api.ts'
import type { Comparison, PairSearch, Region, Slice, SliceResult, WindowResult } from './api.ts'
import { pairedSlices, sliceCloud } from './analysisModel.ts'

export interface StageSelection { region: number }
export interface SlicePlane {
  record: Slice; t1: HTMLImageElement; mask: HTMLImageElement
  pixels: Uint8ClampedArray; maskPixels: Uint8ClampedArray
  cloud: ReturnType<typeof sliceCloud>
}
export interface StageData {
  comparison: Comparison; windows: WindowResult['windows']; planes: SlicePlane[]
  automatic: boolean
}

async function image(path: string, signal: AbortSignal): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const value = new Image()
    const clean = () => { value.onload = null; value.onerror = null; signal.removeEventListener('abort', cancel) }
    const cancel = () => { clean(); value.src = ''; reject(new DOMException('Aborted', 'AbortError')) }
    value.onload = () => { clean(); resolve(value) }
    value.onerror = () => { clean(); reject(new Error('실제 MRI 또는 영역 마스크를 불러오지 못했습니다.')) }
    if (signal.aborted) { cancel(); return }
    signal.addEventListener('abort', cancel, { once: true })
    value.src = path
  })
}

function pixels(value: HTMLImageElement) {
  const canvas = document.createElement('canvas')
  canvas.width = value.naturalWidth; canvas.height = value.naturalHeight
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('MRI 픽셀을 읽을 수 없습니다.')
  context.drawImage(value, 0, 0)
  return context.getImageData(0, 0, canvas.width, canvas.height).data
}

export async function loadStage(regions: Region[], version: string, selection: StageSelection | null,
  signal: AbortSignal, phase: (label: string) => void): Promise<StageData> {
  phase(selection ? '선택 영역 준비' : '대응 영역 관계 검색')
  let a = selection?.region
  const check = (value: { dataset_version: string }) => {
    if (value.dataset_version !== version) throw new Error('데이터 버전이 바뀌었습니다. 화면을 새로 열어 주세요.')
  }
  if (a === undefined) {
    const ranked = await api<PairSearch>('/api/analysis/pairs', signal, { scope: 'homologous', order: 'descending', limit: 1 })
    check(ranked)
    if (!ranked.pairs.length) throw new Error('비교 가능한 대응 영역이 없습니다.')
    a = ranked.pairs[0].region_a
  }
  const [left, right] = hemispherePair(regions, a)
  a = left.label_id
  const b = right.label_id
  const directions = ['Axial', 'Coronal'] as const
  phase('파형·구간별 관계 계산')
  const [comparison, windows, ...sliceResults] = await Promise.all([
    api<Comparison>('/api/analysis/compare', signal, { region_a: a, region_b: b }),
    api<WindowResult>('/api/analysis/windows', signal, { region_a: a, region_b: b, window: 50, step: 10 }),
    ...directions.map(orientation => api<SliceResult>(`/api/regions/${a}/slices?orientation=${orientation}`, signal)),
  ])
  check(comparison); check(windows); sliceResults.forEach(check)
  const records = pairedSlices(sliceResults.flatMap(value => value.slices), a, b)
  phase('두 방향 MRI·영역 마스크 준비')
  const planes = await Promise.all(records.map(async record => {
    const [t1, mask] = await Promise.all(['t1', 'mask'].map(kind => image(`/api/slices/${record.orientation}/${record.slice_index}/${kind}`, signal)))
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    if (t1.naturalWidth !== mask.naturalWidth || t1.naturalHeight !== mask.naturalHeight) throw new Error('MRI와 마스크의 크기가 일치하지 않습니다.')
    const t1Pixels = pixels(t1), maskPixels = pixels(mask)
    return { record, t1, mask, pixels: t1Pixels, maskPixels,
      cloud: sliceCloud(t1Pixels, maskPixels, t1.naturalWidth, t1.naturalHeight, a, b) }
  }))
  if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
  return { comparison, windows: windows.windows, planes, automatic: selection === null }
}
