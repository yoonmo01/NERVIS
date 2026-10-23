import { Fragment, useState } from 'react'
import Markdown from 'react-markdown'
import type { Region } from './api.ts'
import { regionLabel } from './api.ts'
import { displayColor } from './brainVisual.ts'
import { wavePath } from './model.ts'
import { aiErrorMessage, pairSelection } from './conversation.ts'
import type { AIReply, CommandPhase, LocalResult } from './conversation.ts'
import type { StageSelection } from './stageData.ts'

const titles: Record<string, string> = {
  get_dataset_summary: '데이터 개요', get_region_info: '영역 정보', get_timeseries: '시계열',
  compare_regions: '두 영역 비교', find_similar_pairs: '관계 검색', analyze_pair_over_windows: '구간별 관계', get_region_slices: 'MRI 단면',
  analyze_regions_detailed: '자세한 분석',
  analyze_region: '영역 분석',
}
const number = (value: unknown, digits = 3) => typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('ko-KR', { maximumFractionDigits: digits }) : '계산 불가'

const metricLabels: Record<string, string> = {
  thickness_mm: '평균 두께 · mm', volume_mm3: '회백질 부피 · mm³', a: '첫 번째 영역', b: '두 번째 영역',
  difference_b_minus_a: '두 번째 − 첫 번째', relative_difference_percent: '상대 차이 · %',
  region_id: '영역', region_a: '첫 번째 영역', region_b: '두 번째 영역', mean: '평균', std_ddof0: '표준편차',
  iqr: '사분위 범위', rms: 'RMS', rms_adjacent_change: '인접 샘플 변화 RMS', bold: 'BOLD · 원척도', global_zscore: 'z-score · 전체 200점 기준',
  pearson: 'Pearson r', spearman: 'Spearman ρ', correlation: '상관계수', status: '상태', reason: '사유', unit: '단위',
  start_sample: '시작 샘플', end_sample: '끝 샘플', sample_count: '샘플 수', valid_window_count: '유효 창 수',
  min_correlation: '최소 상관', max_correlation: '최대 상관', windows: '창별 결과', parameters: '계산 범위와 설정',
  method: '방법', window: '창 길이 · 샘플', step: '창 간격 · 샘플',
  all_pair_rank: '전체 쌍 중 순위', all_valid_pair_count: '전체 유효 쌍 수', homologous_pair_rank: '좌우 대응 쌍 중 순위', homologous_valid_pair_count: '유효 대응 쌍 수',
  top_pairs: '전체 상위 쌍', related_to_selection: '선택 영역과 높은 상관', pairs: '영역 쌍',
  selected_rms_z: '선택 두 영역 · 편차가 큰 시점', selected_rms_adjacent_change_z: '선택 두 영역 · 변화가 큰 시점',
  all_regions_rms_z: '전체 20영역 · 편차가 큰 시점', all_regions_rms_adjacent_change_z: '전체 20영역 · 변화가 큰 시점',
  sample: '샘플', score: '크기', lags: '지연별 상관', lag_samples: '지연 · 샘플',
  hann_peak_cycles_per_sample: 'Hann 주파수 정점 · cycles/sample', boxcar_peak_cycles_per_sample: 'Boxcar 주파수 정점 · cycles/sample',
  hann_peak_period_samples: 'Hann 정점 주기 · 샘플', boxcar_peak_period_samples: 'Boxcar 정점 주기 · 샘플', resolution_cycles_per_sample: '주파수 해상도 · cycles/sample',
  raw_centered: '원척도 · 평균 제거', within_range_zscore: '구간별 표준화', region_count: '전체 영역 수', constant_region_ids: '상수 신호 영역',
  explained_variance_ratio: '주성분별 설명분산 비율', components: '상위 주성분', component: '주성분 번호', numerical_rank: '유효 주성분 수',
  selected_loadings: '선택 영역의 적재량', top_loadings: '절대 적재량 상위 영역', loading: '적재량',
  deviation_z: '평소 수준에서 편차가 큰 시점', adjacent_change_z: '이전 샘플보다 변화가 큰 시점',
}
const metricText: Record<string, string> = { ok: '계산됨', unavailable: '계산 불가', constant_signal: '상수 신호', all_constant_signals: '모든 신호가 상수', fewer_than_8_samples: '8샘플 미만', fewer_than_4_samples: '겹치는 3샘플 확보에 필요한 길이 부족', numerical_failure: '수치 계산 불가' }

function MetricValues({ value, regions }: { value: unknown; regions: Region[] }) {
  if (value === null || value === undefined) return <>해당 없음 / 계산 불가</>
  if (typeof value !== 'object') return <>{typeof value === 'number' ? number(value, 5) : metricText[String(value)] ?? String(value)}</>
  if (Array.isArray(value)) return value.length ? <ol className="metric-list">{value.map((item, i) => <li key={i}><MetricValues value={item} regions={regions} /></li>)}</ol> : <>계산 가능한 항목 없음</>
  return <dl className="result-metrics">{Object.entries(value).filter(([key]) => !['dataset_version', 'analysis', 'warnings'].includes(key)).map(([key, item]) => <div key={key}><dt>{metricLabels[key] ?? key}</dt><dd>{['region_id', 'region_a', 'region_b'].includes(key) && typeof item === 'number' ? (() => { const region = regions.find(r => r.label_id === item); return region ? regionLabel(region) : String(item) })() : <MetricValues value={item} regions={regions} />}</dd></div>)}</dl>
}

function DetailedResult({ data, regions }: { data: Record<string, unknown>; regions: Region[] }) {
  const sections = { correlations: '두 상관계수', structure: '구조 차이', signal_statistics: '신호 분포와 변동', windows: '이동 창별 관계', rankings: '전체·대응 영역과 비교', major_points: '주요 시점', autocorrelation: '자기상관', spectra: '샘플 기준 스펙트럼', pca: '전체 20영역 PCA' }
  const [section, setSection] = useState('correlations')
  return <><label className="calculation-picker">분석 항목<select value={section} onChange={e => setSection(e.target.value)}>{Object.entries(sections).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>
    {section === 'structure' ? <StructureTable value={data.structure} /> : section === 'signal_statistics' ? <StatisticsTable value={data.signal_statistics} /> : section === 'windows' ? <WindowTable value={data.windows} /> : <MetricValues value={data[section]} regions={regions} />}
    <details className="calculation-basis"><summary>계산 기준</summary><p>구조 상대 차이 = 100 × (두 번째 − 첫 번째) / 두 영역 평균. BOLD 원척도 단위·샘플 간 실제 시간은 미상입니다. z-score는 전체 200점, PCA 구간 표준화는 요청 구간 기준입니다.</p></details></>
}

function StructureTable({ value }: { value: unknown }) {
  if (!value || typeof value !== 'object') return <p>구조 계산 결과가 없습니다.</p>
  return <table className="result-table"><caption>구조 비교 · 선택 순서 기준</caption><thead><tr><th>지표</th><th>첫 영역</th><th>둘째 영역</th><th>차이</th></tr></thead><tbody>{Object.entries(value).map(([key, row]) => {
    const metric = row as Record<string, unknown>
    return <Fragment key={key}><tr><th>{metricLabels[key]}</th><td>{number(metric.a)}</td><td>{number(metric.b)}</td><td>{number(metric.difference_b_minus_a)}</td></tr>{typeof metric.relative_difference_percent === 'number' && <tr><th colSpan={3}>상대 차이 · %</th><td>{number(metric.relative_difference_percent)}</td></tr>}</Fragment>
  })}</tbody></table>
}

function StatisticsTable({ value }: { value: unknown }) {
  const rows = value as { region_id: number; bold: Record<string, number>; global_zscore: Record<string, number> }[]
  if (!Array.isArray(rows) || rows.length !== 2) return <p>신호 통계가 없습니다.</p>
  return <>{(['bold', 'global_zscore'] as const).map(scale => <table className="result-table" key={scale}><caption>{metricLabels[scale]}</caption><thead><tr><th>지표</th><th>첫 영역</th><th>둘째 영역</th></tr></thead><tbody>{Object.keys(rows[0][scale]).map(key => <tr key={key}><th>{metricLabels[key]}</th><td>{number(rows[0][scale][key])}</td><td>{number(rows[1][scale][key])}</td></tr>)}</tbody></table>)}</>
}

function WindowTable({ value }: { value: unknown }) {
  const result = value as { windows?: { start_sample: number; end_sample: number; correlation: number | null }[]; min_correlation?: number; max_correlation?: number }
  if (!result || !Array.isArray(result.windows)) return <p>이동 창 결과가 없습니다.</p>
  return <><p>최소 {number(result.min_correlation)} · 최대 {number(result.max_correlation)}</p><table className="result-table"><thead><tr><th>구간</th><th>상관계수</th></tr></thead><tbody>{result.windows.map(row => <tr key={row.start_sample}><td>{row.start_sample}~{row.end_sample}</td><td>{number(row.correlation)}</td></tr>)}</tbody></table></>
}

function Result({ result, regions, locked, onSelect }: { result: LocalResult; regions: Region[]; locked: boolean; onSelect: (selection: StageSelection) => void }) {
  const d = result.data, p = result.parameters
  const label = (id: unknown) => { const r = regions.find(r => r.label_id === id); return r ? regionLabel(r) : '영역 정보 없음' }
  const rows = (Array.isArray(d.pairs) ? d.pairs : Array.isArray(d.windows) ? d.windows : []) as Record<string, unknown>[]
  return <article className="command-result"><h3>{titles[result.tool]}</h3>
    {result.tool === 'get_dataset_summary' && <p>영역 {number(d.region_count, 0)}개 · 샘플 {number(d.sample_count, 0)}개 · 단면 {number(d.slice_count, 0)}개<br />샘플 간 실제 시간 간격은 미상입니다.</p>}
    {result.tool === 'get_region_info' && d.region && typeof d.region === 'object' ? <p>{label(p.region_id)}<br />평균 두께 {number((d.region as Region).thickness_mm)} mm · 회백질 부피 {number((d.region as Region).volume_mm3, 0)} mm³</p> : null}
    {result.tool === 'compare_regions' && <><p>{label(p.region_a)} / {label(p.region_b)}<br />샘플 {String(p.start)}~{String(p.end)} · {p.method === 'spearman' ? 'Spearman ρ' : 'Pearson r'} {number(d.correlation)}</p><StructureTable value={d.structure} /></>}
    {result.tool === 'analyze_regions_detailed' && <><p>{label(p.region_a)} / {label(p.region_b)} · 샘플 {String(p.start)}~{String(p.end)}</p><DetailedResult data={d} regions={regions} /></>}
    {result.tool === 'analyze_region' && <><p>{label(p.region_id)} · 샘플 {String(p.start)}~{String(p.end)}</p><SingleRegionResult data={d} regions={regions} /></>}
    {result.tool === 'get_region_slices' && <p>{label(p.region_id)} · {String(p.orientation)}<br />추천 단면 {d.recommended_slice && typeof d.recommended_slice === 'object' ? String((d.recommended_slice as { slice_index: number }).slice_index) : '없음'} · 등록 단면 {Array.isArray(d.slices) ? d.slices.length : 0}개</p>}
    {result.tool === 'find_similar_pairs' && <ol className="command-pairs">{rows.map((row, i) => <li key={i}><button disabled={locked} onClick={() => onSelect(pairSelection(row.region_a, row.region_b, p))}>{label(row.region_a)} / {label(row.region_b)}<b>{number(row.correlation)}</b><small>이 쌍 보기 ↗</small></button></li>)}</ol>}
    {result.tool === 'analyze_pair_over_windows' && <><p>{label(p.region_a)} / {label(p.region_b)} · 샘플 {String(p.start)}~{String(p.end)}</p><details><summary>구간별 계산 {rows.length}개</summary><ul>{rows.map((row, i) => <li key={i}>{String(row.start_sample)}~{String(row.end_sample)} · {number(row.correlation)}</li>)}</ul></details></>}
    {result.tool === 'get_timeseries' && <SignalResult result={result} regions={regions} />}
    {d.status === 'unavailable' && <p>선택 구간에서는 상관을 계산할 수 없습니다.</p>}
  </article>
}

function SingleRegionResult({ data, regions }: { data: Record<string, unknown>; regions: Region[] }) {
  const [section, setSection] = useState('signal_statistics')
  const region = data.region as Region | undefined
  return <>
    <p>평균 두께 {number(region?.thickness_mm)} mm · 회백질 부피 {number(region?.volume_mm3, 0)} mm³</p>
    <label className="calculation-picker">분석 항목<select value={section} onChange={e => setSection(e.target.value)}><option value="signal_statistics">신호 분포와 변동</option><option value="major_points">주요 변화 시점</option></select></label>
    <MetricValues value={data[section]} regions={regions} />
    <details className="calculation-basis"><summary>계산 기준</summary><p>z-score는 전체 200개 샘플 기준입니다. 주요 시점은 최소 10샘플 간격으로 최대 5개를 선택하며, 변화 시점은 뒤쪽 샘플에 표시합니다. 샘플 간 실제 시간과 BOLD 원척도 단위는 미상입니다.</p></details>
  </>
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

export function CalculationResults({ reply, regions, locked, onSelect }: { reply: AIReply; regions: Region[]; locked: boolean; onSelect: (selection: StageSelection) => void }) {
  const [selectedId, setSelectedId] = useState('')
  const selected = reply.results.find(result => result.result_id === selectedId) ?? reply.results[0]
  return <section className="calculation-results" aria-label="계산 결과">{reply.results.length > 1 && <label className="calculation-picker">계산 선택<select value={selected?.result_id ?? ''} onChange={e => setSelectedId(e.target.value)}>{reply.results.map((result, index) => <option key={result.result_id} value={result.result_id}>{index+1}. {titles[result.tool]}</option>)}</select></label>}{selected ? <Result key={selected.result_id} result={selected} regions={regions} locked={locked} onSelect={onSelect} /> : <p>계산 결과가 없습니다.</p>}</section>
}

export default function ConversationPanel({ phase, command, reply, error, regions, locked, onSelect, onClose, docked = false }: {
  phase: CommandPhase; command: string; reply: AIReply | null; error: string; regions: Region[]; locked: boolean;
  onSelect: (selection: StageSelection) => void; onClose: () => void; docked?: boolean;
}) {
  if (phase === 'idle') return null
  const briefing = reply?.results.some(r => r.tool === 'get_daily_briefing' || r.tool === 'get_weather')
  const analysisReply = reply ? { ...reply, results: reply.results.filter(r => r.tool !== 'get_daily_briefing' && r.tool !== 'get_weather') } : null
  return <aside className="conversation-result" aria-label="NERVIS 요청과 결과" aria-busy={locked}>
    <div className="conversation-result-heading"><span>NERVIS</span>{!docked && <button disabled={locked} onClick={onClose} aria-label="대화 결과 닫기">×</button>}</div>
    <p className="submitted-command">{command}</p>
    <p role={error ? 'alert' : 'status'} className={`request-state${error ? ' has-error' : ''}`}>{error || (phase === 'requesting' ? '요청하신 내용을 확인하고 있어요.' : phase === 'applying' ? '결과를 화면에 정리하고 있어요.' : reply?.status === 'partial' ? briefing ? '조회 결과는 받았지만 설명을 마무리하지 못했어요.' : '계산은 완료했지만 설명을 마무리하지 못했어요. 계산 결과를 확인해 주세요.' : reply?.results.length ? briefing ? '브리핑이 준비됐어요.' : '분석 결과가 준비됐어요.' : '답변이 준비됐어요.')}</p>
    {reply?.model_acknowledgement && phase !== 'requesting' && <div className="model-acknowledgement"><Markdown skipHtml disallowedElements={['img', 'a']} unwrapDisallowed>{reply.model_acknowledgement}</Markdown></div>}
    {reply?.warning && <p className="result-warning" role="status">{aiErrorMessage(reply.warning)}</p>}
    {!docked && analysisReply && analysisReply.results.length > 0 && <details className="local-results" open={!analysisReply.model_acknowledgement || analysisReply.results.some(r => ['find_similar_pairs', 'get_dataset_summary', 'get_timeseries', 'analyze_regions_detailed'].includes(r.tool))}><summary>계산 결과</summary><CalculationResults reply={analysisReply} regions={regions} locked={locked} onSelect={onSelect} /></details>}
  </aside>
}
