export interface Region {
  label_id: number
  hemisphere: 'Left' | 'Right'
  name_ko: string
  region_name: string
  color_rgb: number[]
  thickness_mm: number
  volume_mm3: number
  contralateral_id: number
}
export interface Summary {
  dataset_version: string
  region_count: number
  sample_count: number
  slice_count: number
}
export interface Slice {
  orientation: 'Axial' | 'Coronal'
  slice_index: number
  pixel_counts: Record<string, number>
}
export interface SliceResult {
  dataset_version: string
  recommended_slice: Slice | null
  slices: Slice[]
}
export interface PairSearch { dataset_version: string; pairs: { region_a: number; region_b: number; correlation: number }[] }
export interface WindowResult {
  dataset_version: string
  windows: { start_sample: number; end_sample: number; correlation: number | null; status: string }[]
}
export interface Comparison {
  dataset_version: string
  correlation: number | null
  status: string
  samples: number[]
  zscore: number[][]
  regions: Region[]
}

export class ApiError extends Error {
  code: string
  status: number
  constructor(status: number, code: string) {
    super(`로컬 서버 요청에 실패했습니다 (${status}).`)
    this.code = code; this.status = status
  }
}

export async function api<T>(path: string, signal: AbortSignal, body?: object): Promise<T> {
  if (!path.startsWith('/api/')) throw new Error('Only local API routes are allowed')
  const response = await fetch(path, {
    signal,
    method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, error && typeof error.detail === 'string' ? error.detail : 'request_failed')
  }
  return response.json()
}

export function regionLabel(region: Region) {
  return `${region.hemisphere === 'Left' ? '좌' : '우'} ${region.name_ko}`
}
