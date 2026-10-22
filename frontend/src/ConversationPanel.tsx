import type { Region } from './api.ts'
import { regionLabel } from './api.ts'
import { displayColor } from './brainVisual.ts'
import { wavePath } from './model.ts'
import { pairSelection } from './conversation.ts'
import type { AIReply, CommandPhase, LocalResult } from './conversation.ts'
import type { StageSelection } from './stageData.ts'

const titles: Record<string, string> = {
  get_dataset_summary: '데이터 개요', get_region_info: '영역 정보', get_timeseries: '시계열',
  compare_regions: '두 영역 비교', find_similar_pairs: '관계 검색', analyze_pair_over_windows: '구간별 관계', get_region_slices: 'MRI 단면',
}
const number = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '계산 불가'

function Result({ result, regions, locked, onSelect }: { result: LocalResult; regions: Region[]; locked: boolean; onSelect: (selection: StageSelection) => void }) {
  const d = result.data, p = result.parameters
  const label = (id: unknown) => { const r = regions.find(r => r.label_id === id); return r ? regionLabel(r) : '영역 정보 없음' }
  const rows = (Array.isArray(d.pairs) ? d.pairs : Array.isArray(d.windows) ? d.windows : []) as Record<string, unknown>[]
  return <article className="command-result"><h3>{titles[result.tool]}</h3>
    {result.tool === 'get_dataset_summary' && <p>영역 {number(d.region_count, 0)}개 · 샘플 {number(d.sample_count, 0)}개 · 단면 {number(d.slice_count, 0)}개<br />샘플 간 실제 시간 간격은 미상입니다.</p>}
    {result.tool === 'get_region_info' && d.region && typeof d.region === 'object' ? <p>{label(p.region_id)}<br />평균 두께 {number((d.region as Region).thickness_mm)} mm · 회백질 부피 {number((d.region as Region).volume_mm3, 0)} mm³</p> : null}
    {result.tool === 'compare_regions' && <p>{label(p.region_a)} / {label(p.region_b)}<br />샘플 {String(p.start)}~{String(p.end)} · {p.method === 'spearman' ? 'Spearman ρ' : 'Pearson r'} {number(d.correlation)}</p>}
    {result.tool === 'get_region_slices' && <p>{label(p.region_id)} · {String(p.orientation)}<br />추천 단면 {d.recommended_slice && typeof d.recommended_slice === 'object' ? String((d.recommended_slice as { slice_index: number }).slice_index) : '없음'} · 등록 단면 {Array.isArray(d.slices) ? d.slices.length : 0}개</p>}
    {result.tool === 'find_similar_pairs' && <ol className="command-pairs">{rows.map((row, i) => <li key={i}><button disabled={locked} onClick={() => onSelect(pairSelection(row.region_a, row.region_b, p))}>{label(row.region_a)} / {label(row.region_b)}<b>{number(row.correlation)}</b><small>이 쌍 보기 ↗</small></button></li>)}</ol>}
    {result.tool === 'analyze_pair_over_windows' && <><p>{label(p.region_a)} / {label(p.region_b)} · 샘플 {String(p.start)}~{String(p.end)}</p><details><summary>구간별 계산 {rows.length}개</summary><ul>{rows.map((row, i) => <li key={i}>{String(row.start_sample)}~{String(row.end_sample)} · {number(row.correlation)}</li>)}</ul></details></>}
    {result.tool === 'get_timeseries' && <SignalResult result={result} regions={regions} />}
    {d.status === 'unavailable' && <p>선택 구간에서는 상관을 계산할 수 없습니다.</p>}
  </article>
}

function SignalResult({ result, regions }: { result: LocalResult; regions: Region[] }) {
  const values = result.data.zscore, samples = result.data.samples, ids = result.data.region_ids
  if (!Array.isArray(values) || !Array.isArray(samples) || !Array.isArray(ids) || !values.length ||
      values.some(row => !Array.isArray(row) || row.length !== ids.length || row.some(v => typeof v !== 'number' || !Number.isFinite(v)))) return <p>파형 표시 형식을 확인하지 못했습니다.</p>
  const rows = values as number[][], extent = Math.max(3, ...rows.flat().map(Math.abs))
  if (rows.length === 1) return <><p>샘플 {String(samples[0])} · z-score</p>{ids.map((id, column) => {
    const region = regions.find(r => r.label_id === id)
    return <p key={column}>{region ? regionLabel(region) : '영역 정보 없음'}: {number(rows[0][column])}</p>
  })}</>
  return <><p>샘플 {String(samples[0])}~{String(samples.at(-1))} · 전체 기록 기준 z-score</p><svg className="command-signals" viewBox="0 0 1000 120" preserveAspectRatio="none" role="img" aria-label="요청한 모든 영역의 표준화 파형">{ids.map((id, column) => {
    const region = regions.find(r => r.label_id === id)
    return <path key={column} d={wavePath(rows.map(row => row[column]), extent)} fill="none" stroke={region ? `rgb(${displayColor(region).join(',')})` : '#b7d9e8'} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
  })}</svg><p>{ids.map(id => { const r = regions.find(r => r.label_id === id); return r ? regionLabel(r) : '영역 정보 없음' }).join(' · ')}</p></>
}

export default function ConversationPanel({ phase, command, reply, error, regions, locked, onSelect, onClose }: {
  phase: CommandPhase; command: string; reply: AIReply | null; error: string; regions: Region[]; locked: boolean;
  onSelect: (selection: StageSelection) => void; onClose: () => void;
}) {
  if (phase === 'idle') return null
  return <aside className="conversation-result" aria-label="NERVIS 요청과 결과" aria-busy={locked}>
    <div className="conversation-result-heading"><span>NERVIS</span><button disabled={locked} onClick={onClose} aria-label="대화 결과 닫기">×</button></div>
    <p className="submitted-command">{command}</p>
    <p role={error ? 'alert' : 'status'} className={`request-state${error ? ' has-error' : ''}`}>{error || (phase === 'requesting' ? '명령 해석·로컬 도구 실행 중' : phase === 'applying' ? '분석 완료 · 화면 준비 중' : reply?.status === 'partial' ? '로컬 분석 완료 · 모델의 후속 응답 미완료' : reply?.results.length ? '결과 적용 완료' : '응답 완료')}</p>
    {reply?.model_acknowledgement && phase !== 'requesting' && <p className="model-acknowledgement">{reply.model_acknowledgement}</p>}
    {reply && <details className="local-results" open={!reply.model_acknowledgement || reply.results.some(r => r.tool === 'find_similar_pairs' || r.tool === 'get_dataset_summary' || r.tool === 'get_timeseries')}><summary>로컬 계산 결과 {reply.results.length}개</summary>{reply.results.map(result => <Result key={result.result_id} result={result} regions={regions} locked={locked} onSelect={onSelect} />)}</details>}
  </aside>
}
