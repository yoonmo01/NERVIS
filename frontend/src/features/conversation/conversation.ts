import type { Comparison, Slice, WindowResult } from '../analysis/api.ts'
import type { StageSelection } from '../analysis/stageData.ts'
import type { CoreState } from '../../components/model.ts'
import { checkBriefing } from '../briefing/briefing.ts'
import { checkTaskResult, isTaskTool } from '../briefing/tasks.ts'
import type { SpeechSegment } from '../speech/presentation.ts'

export type CommandPhase = 'idle' | 'requesting' | 'applying' | 'complete' | 'error'
export interface AIStatus { enabled: boolean; model: string; remaining_process_requests: number | null; busy: boolean }
export interface LocalResult { result_id: string; tool: string; parameters: Record<string, unknown>; data: Record<string, unknown> }
export interface AIReply { status: 'ok' | 'partial'; model_acknowledgement: string | null; results: LocalResult[]; warning: string | null; segments?: SpeechSegment[]; explanation_source?: 'model' | 'local_results' | 'local_receipt'; explanation_error?: string | null }
export interface ViewContext { selected_region_ids: number[]; start: number; end: number }
export interface ViewRequest { id: number; selection: StageSelection }

const toolNames = ['get_dataset_summary', 'get_region_info', 'get_timeseries', 'compare_regions', 'find_similar_pairs', 'analyze_pair_over_windows', 'get_region_slices', 'analyze_regions_detailed', 'analyze_region']

export function pending(phase: CommandPhase) { return phase === 'requesting' || phase === 'applying' }

export function interfaceState(phase: CommandPhase, connected: boolean, enabled: boolean, busy: boolean, preview = false): CoreState {
  if (phase === 'error' || !connected) return 'error'
  if (phase === 'requesting' || busy) return 'processing'
  if (phase === 'applying') return 'analyzing'
  if (preview) return 'preview'
  return enabled ? 'standby' : 'paused'
}

export function correlationLabel(start: number, end: number, window: boolean) {
  return `${window ? '이동 창' : start === 1 && end === 200 ? '전체 구간' : '분석 구간'} ${start}~${end}`
}

function integer(value: unknown, low: number, high: number): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < low || value > high) throw new Error('분석 응답의 범위가 올바르지 않습니다.')
  return value
}

export function checkedReply(value: AIReply, version: string): AIReply {
  if (!value || !['ok', 'partial'].includes(value.status) || !Array.isArray(value.results) || value.results.length > 6 ||
      !(value.model_acknowledgement === null || typeof value.model_acknowledgement === 'string')) throw new Error('AI 응답 형식이 올바르지 않습니다.')
  const ids = new Set<string>()
  for (const result of value.results) {
    if (!result || typeof result.result_id !== 'string' || ids.has(result.result_id) || !result.parameters || !result.data) throw new Error('결과 형식이 올바르지 않습니다.')
    if (isTaskTool(result.tool)) checkTaskResult(result.data, result.tool)
    else if (result.tool === 'get_daily_briefing' || result.tool === 'get_weather') checkBriefing(result.data, result.tool)
    else if (!toolNames.includes(result.tool) || result.data.analysis !== result.tool || result.data.dataset_version !== version) throw new Error('분석 결과의 도구 또는 데이터 버전이 일치하지 않습니다.')
    ids.add(result.result_id)
  }
  return value
}

export function pairSelection(a: unknown, b: unknown, parameters: Record<string, unknown>): StageSelection {
  const region = integer(a, 1, 20), region_b = integer(b, 1, 20)
  const start = integer(parameters.start ?? 1, 1, 200), end = integer(parameters.end ?? 200, start, 200)
  if (region === region_b || end - start < 2 || !['pearson', 'spearman'].includes(String(parameters.method ?? 'pearson'))) throw new Error('비교 대상 또는 분석 구간이 올바르지 않습니다.')
  return { region, region_b, start, end, method: (parameters.method ?? 'pearson') as 'pearson' | 'spearman' }
}

export function viewSelection(reply: AIReply): StageSelection | null {
  let selection: StageSelection | null = null
  // Prefer the final explicit calculation over supporting info tools in the same batch.
  for (const result of reply.results) {
    const p = result.parameters
    if (result.tool === 'compare_regions' || result.tool === 'analyze_pair_over_windows' || result.tool === 'analyze_regions_detailed') {
      selection = pairSelection(p.region_a, p.region_b, p)
      if (result.tool === 'compare_regions') selection.comparison = result.data as unknown as Comparison
      else {
        selection.window = integer(p.window ?? 50, 3, selection.end! - selection.start! + 1)
        selection.step = integer(p.step ?? 10, 1, selection.end! - selection.start! + 1)
        selection.windowResult = (result.tool === 'analyze_regions_detailed' ? result.data.windows : result.data) as unknown as WindowResult
        if (result.tool === 'analyze_regions_detailed') selection.comparison = result.data.comparison as unknown as Comparison
      }
    }
  }
  if (selection) return selection
  const single = reply.results.find(r => r.tool === 'analyze_region')
  if (single) {
    const start = integer(single.parameters.start ?? 1, 1, 200)
    return { region: integer(single.parameters.region_id, 1, 20), single: true,
      start, end: integer(single.parameters.end ?? 200, start, 200),
      comparison: single.data.comparison as unknown as Comparison }
  }
  const ranked = reply.results.find(r => r.tool === 'find_similar_pairs')
  if (ranked && Array.isArray(ranked.data.pairs) && ranked.data.pairs.length) {
    const pair = ranked.data.pairs[0] as Record<string, unknown>
    return pairSelection(pair.region_a, pair.region_b, ranked.parameters)
  }
  const timeseries = reply.results.find(r => r.tool === 'get_timeseries')
  if (timeseries && Array.isArray(timeseries.parameters.region_ids) && timeseries.parameters.region_ids.length === 2) {
    if (Number(timeseries.parameters.end ?? 200) - Number(timeseries.parameters.start ?? 1) < 2) return null
    return pairSelection(...timeseries.parameters.region_ids as [number, number], timeseries.parameters)
  }
  const region = reply.results.find(r => r.tool === 'get_region_slices') ?? reply.results.find(r => r.tool === 'get_region_info')
  return region ? { region: integer(region.parameters.region_id, 1, 20),
    recommendedSlice: region.tool === 'get_region_slices' && region.data.recommended_slice ? region.data.recommended_slice as Slice : undefined } : null
}

export function aiErrorMessage(code: string): string {
  const messages: Record<string, string> = {
    invalid_tool_arguments: 'AI가 만든 작업 인자의 형식을 확인하지 못했습니다. 도구는 실행하지 않았습니다.',
    result_serialization_failed: '서버 결과를 화면으로 전달하지 못했습니다. 저장은 완료됐을 수 있으니 대화 기록을 확인해 주세요. 자동 재전송하지 않습니다.',
    request_failed: '서버 처리 중 오류가 발생했습니다. 서버 기록을 확인해 주세요. 자동 재전송하지 않습니다.',
    ai_budget_exhausted_or_disabled: 'AI 호출이 꺼져 있거나 승인된 호출 예산을 모두 사용했습니다.',
    planner_session_required: '할 일 변경은 대화 세션에서 요청해 주세요.',
    task_target_no_longer_exists: '대상 할 일이 없어졌습니다. 이름을 다시 알려 주세요.',
    invalid_task_fields: '날짜·시간 등 할 일 정보를 확인해 주세요.',
    duplicate_actions_in_task_batch: '동일한 작업이 한 요청에 중복되어 있습니다. 하나씩 정리해 다시 말씀해 주세요.',
    task_actions_required: '등록하거나 바꿀 할 일을 알려 주세요.',
    task_write_must_be_single_batch: '할 일 변경 요청을 하나의 작업 묶음으로 다시 말씀해 주세요.',
    ai_request_in_progress: '서버에서 이전 요청을 처리 중입니다. 완료 후 새 명령을 보내 주세요.',
    'AI configuration is invalid': '서버의 AI 설정을 확인해 주세요.',
    gateway_http_401: 'Gateway 인증을 확인해 주세요.', gateway_http_403: '해당 모델의 사용 권한을 확인해 주세요.',
    gateway_http_402: 'Gateway 크레딧을 확인해 주세요.', gateway_http_429: 'Gateway 사용 제한에 도달했습니다. 자동 재시도하지 않습니다.',
    gateway_connection_or_json_error: 'Gateway 응답을 확인하지 못했습니다. 이미 과금됐을 수 있어 자동 재전송하지 않습니다.',
    invalid_grounded_explanation: 'AI 설명의 응답 형식이나 근거를 확인하지 못했습니다. 실제 조회·분석 결과는 유지됩니다.',
  }
  return messages[code] ?? '요청을 완료하지 못했습니다. 자동 재전송하지 않았습니다.'
}
