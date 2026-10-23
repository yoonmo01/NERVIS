import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, ReactNode } from 'react'
import { regionLabel } from './api.ts'
import type { Region } from './api.ts'
import { displayColor } from './brainVisual.ts'
import { advanceSample } from './analysisModel.ts'
import { wavePath } from './model.ts'
import { loadStage } from './stageData.ts'
import type { ViewContext, ViewRequest } from './conversation.ts'
import { correlationLabel } from './conversation.ts'
import type { StageData, StageSelection } from './stageData.ts'
import BrainStage, { SliceCanvas } from './BrainStage.tsx'

const roiStyle = (region: Region) => ({ '--roi-color': `rgb(${displayColor(region).join(',')})` } as CSSProperties)

function RegionCard({ data, column, sample, expanded = false }: { data: StageData; column: number; sample: number; expanded?: boolean }) {
  const region = data.comparison.regions[column]
  const plane = [...data.planes].sort((a, b) => (b.record.pixel_counts[String(region.label_id)] ?? 0) - (a.record.pixel_counts[String(region.label_id)] ?? 0))[0]
  const available = column ? plane.cloud.boundsB : plane.cloud.boundsA
  return <div className={`region-card${expanded ? ' region-card--expanded' : ''}`} style={roiStyle(region)}>
    <div className="region-card-image">{available ? <SliceCanvas plane={plane} region={column} regions={data.comparison.regions} values={data.comparison.zscore[sample - data.comparison.samples[0]]} label={`${regionLabel(region)} 실제 단면 확대`} /> : <span>이 단면에는 영역 없음</span>}</div>
    <div><small>{region.hemisphere === 'Left' ? '좌뇌 · LEFT' : '우뇌 · RIGHT'}</small><h3>{regionLabel(region)}</h3></div>
  </div>
}

export default function AnalysisView({ regions, version, active, blocked, reduced, onBusyChange, request, onApplied, onContext, response, calculations, tab, onTab }: {
  regions: Region[]; version: string; active: boolean; blocked: boolean; reduced: boolean; onBusyChange: (value: boolean) => void; request: ViewRequest | null; onApplied: (id: number, error?: string) => void; onContext: (value: ViewContext) => void;
  response: ReactNode; calculations: ReactNode; tab: 'mri' | 'response' | 'calculations'; onTab: (tab: 'mri' | 'response' | 'calculations') => void;
}) {
  const [selection, setSelection] = useState<StageSelection | null>(() => request?.selection ?? null)
  const [data, setData] = useState<StageData | null>(null)
  const [phase, setPhase] = useState('대응 영역 관계 검색')
  const [error, setError] = useState('')
  const [modelReady, setModelReady] = useState(false)
  const [cameraToolbar, setCameraToolbar] = useState<HTMLDivElement | null>(null)
  const onModelReady = useCallback(() => setModelReady(true), [])
  const onModelError = useCallback(() => {
    const message = '3D 모형을 불러오지 못했습니다. 로컬 화면 준비를 다시 시도해 주세요.'
    setError(message); setPlaying(false); onBusyChange(false); if (request) onApplied(request.id, message)
  }, [request, onApplied, onBusyChange])
  const [attempt, setAttempt] = useState(0)
  const [cursor, setCursor] = useState(1)
  const [playing, setPlaying] = useState(false)
  const [visible, setVisible] = useState(() => !document.hidden)
  const [windowIndex, setWindowIndex] = useState<number | null>(null)
  const [detail, setDetail] = useState<'regions' | 'mri' | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const autoPlay = useRef(!reduced)
  useEffect(() => { autoPlay.current = !reduced; if (reduced) setPlaying(false) }, [reduced])

  useEffect(() => {
    const controller = new AbortController()
    onBusyChange(true); setData(null); setError(''); setPlaying(false); setDetail(null); setModelReady(false)
    loadStage(regions, version, selection, controller.signal, label => { if (!controller.signal.aborted) setPhase(label) })
      .then(result => {
        if (controller.signal.aborted) return
        setData(result); setCursor(result.comparison.samples[0]); setWindowIndex(null); setPhase('로컬 분석 완료'); setPlaying(autoPlay.current && !document.hidden)
      }).catch(reason => {
        if (!controller.signal.aborted) {
          const message = reason instanceof Error ? reason.message : '로컬 분석을 완료하지 못했습니다.'
          setError(message); onBusyChange(false); if (request) onApplied(request.id, message)
        }
      })
    return () => { controller.abort(); onBusyChange(false) }
  }, [regions, version, selection, attempt, onBusyChange, request, onApplied])

  useEffect(() => {
    if (!data || !modelReady) return
    onBusyChange(false); if (request) onApplied(request.id)
  }, [data, modelReady, request, onApplied, onBusyChange])

  const selectedWindow = windowIndex === null ? null : data?.windows[windowIndex]
  const baseStart = data?.comparison.samples[0] ?? 1, baseEnd = data?.comparison.samples.at(-1) ?? 200
  const start = selectedWindow?.start_sample ?? baseStart, end = selectedWindow?.end_sample ?? baseEnd
  useEffect(() => {
    if (data) onContext({ selected_region_ids: data.comparison.regions.map(r => r.label_id), start, end })
  }, [data, start, end, onContext])
  const sampleIndex = cursor - baseStart
  const plotX = (sample: number) => (sample - baseStart) / Math.max(1, baseEnd - baseStart) * 1000
  useEffect(() => { if (!active || blocked) setPlaying(false) }, [active, blocked])
  useEffect(() => {
    const pause = () => { setVisible(!document.hidden); if (document.hidden) setPlaying(false) }
    document.addEventListener('visibilitychange', pause)
    return () => document.removeEventListener('visibilitychange', pause)
  }, [])
  useEffect(() => {
    if (!playing || !data || !active || blocked || !visible) return
    const timer = setInterval(() => setCursor(value => advanceSample(value, start, end)), 100)
    return () => clearInterval(timer)
  }, [playing, data, active, blocked, visible, start, end])
  useEffect(() => {
    if (detail !== null && dialog.current && !dialog.current.open) dialog.current.showModal()
    else if (detail === null && dialog.current?.open) dialog.current.close()
  }, [detail])

  const showDetail = (value: 'regions' | 'mri') => { setPlaying(false); setDetail(value) }
  const chooseWindow = (index: number | null) => {
    setPlaying(false); setWindowIndex(index); setCursor(index === null ? baseStart : data!.windows[index].start_sample)
  }
  const region = data?.comparison.regions[0] ?? regions.find(item => item.label_id === selection?.region)
  const choices = regions.filter(item => item.hemisphere === 'Left')
  const categoryId = region?.hemisphere === 'Right' ? region.contralateral_id : region?.label_id
  const single = data?.comparison.regions.length === 1
  const counterparts = data && data.comparison.regions[0].contralateral_id === data.comparison.regions[1]?.label_id
  const pairTitle = single && data ? regionLabel(data.comparison.regions[0]) : counterparts ? `${region?.name_ko} · 좌우 영역` : '선택한 두 영역'
  const extent = data ? Math.max(3, ...data.comparison.zscore.flat().map(Math.abs)) : 3
  const fraction = data ? (cursor - baseStart) / Math.max(1, data.comparison.samples.length - 1) : 0
  const currentCorrelation = selectedWindow ? selectedWindow.correlation : data?.comparison.correlation
  const activeTab = tab === 'calculations' && calculations ? 'calculations' : tab !== 'mri' && response ? 'response' : 'mri'


  return <section className={`analysis-workspace analysis-workspace--expanded${data ? ' stage-complete' : ''}`} aria-label="뇌 데이터 탐색" aria-busy={!data && !error}>
    <aside className="selection-panel framed">
      <p className="eyebrow">IMAGES & RESULTS</p><h2>영역과 결과</h2>
      <div className="analysis-tabs" role="group" aria-label="왼쪽 패널 선택"><button aria-pressed={activeTab === 'mri'} onClick={() => onTab('mri')}>MRI</button><button aria-pressed={activeTab === 'response'} disabled={!response} onClick={() => onTab('response')}>응답</button><button aria-pressed={activeTab === 'calculations'} disabled={!calculations} onClick={() => onTab('calculations')}>계산 결과</button></div>
      <div hidden={activeTab !== 'response'} className="response-dock">{response}</div>
      <div hidden={activeTab !== 'calculations'} className="response-dock calculation-dock">{calculations}</div>
      <div hidden={activeTab !== 'mri'}>
      <div className="inline-region-selection">
        <label htmlFor="region-select">선택 영역</label>
        <select id="region-select" value={categoryId ?? choices[0].label_id} disabled={!data && !error} onChange={e => setSelection({ region: Number(e.target.value) })}>{choices.map(item => <option key={item.label_id} value={item.label_id}>{item.name_ko}</option>)}</select>
      </div>
      {data ? <>
        <button className="mri-pair-button" onClick={() => showDetail('mri')} aria-label="MRI 두 단면 확대">{data.planes.map(plane => <span key={plane.record.orientation}>
          <SliceCanvas plane={plane} regions={data.comparison.regions} values={data.comparison.zscore[sampleIndex]} label={`${plane.record.orientation} 실제 MRI와 선택 영역 마스크`} />
          <small>{plane.record.orientation === 'Axial' ? 'Axial · 수평면' : 'Coronal · 관상면'} ↗</small>
        </span>)}</button>
        <button className="roi-pair-button" onClick={() => showDetail('regions')} aria-label={`${pairTitle} 확대`}><span className="roi-pair-title">{pairTitle} ↗</span><div className="roi-image-pair">{data.comparison.regions.map((_, column) => <RegionCard key={column} data={data} column={column} sample={cursor} />)}</div></button>
      </> : <p className="stage-wait">{error ? '분석을 다시 실행해 주세요.' : phase}</p>}
      </div>
    </aside>

    <div className="analysis-stage framed" role="group" aria-label="뇌 모형과 신호 분석">
    <div className="brain-panel">
      <div className="panel-heading brain-heading"><span className="eyebrow">3D BRAIN</span><div ref={setCameraToolbar} className="brain-toolbar" /></div>
      {error ? <div className="empty-state" role="alert"><p>{error}</p><button onClick={() => setAttempt(value => value + 1)}>분석 다시 시도</button></div>
        : !data ? <div className="empty-state" role="status"><span className="loading-mark" /><strong>{phase}</strong><small>실제 로컬 데이터 처리 중</small></div>
        : <div className="brain-stage-body">
          <BrainStage onReady={onModelReady} onError={onModelError} data={data} sample={cursor} active={active && !blocked && visible} reduced={reduced} toolbarTarget={cameraToolbar} />
          <span className="stage-sample">SAMPLE <b>{cursor.toString().padStart(3, '0')}</b></span>
        </div>}
      <div className="brain-caption"><span className="live-dot" />일반 뇌 모형 · 개략 위치</div>
    </div>
    <div className="signal-panel">
      <div className="panel-heading signal-heading"><div className="signal-legend" role="group" aria-label="파형 범례">{data ? data.comparison.regions.map((item, column) => <span key={item.label_id} style={roiStyle(item)}><i className={column ? 'is-dashed' : ''} aria-hidden="true" />{regionLabel(item)}<span className="sr-only"> · {column ? '점선' : '실선'}</span></span>) : <span className="eyebrow">영역 신호</span>}</div><span className="quiet">신호 크기에 따른 밝기 변화</span></div>
      {data ? <>
        <div className="stage-chart-wrap"><svg viewBox="0 0 1000 120" preserveAspectRatio="none" role="img" aria-label={single ? '선택 영역의 실제 표준화 BOLD 파형' : '두 영역의 실제 표준화 BOLD 파형'} onPointerDown={event => {
          const box = event.currentTarget.getBoundingClientRect()
          setPlaying(false); setCursor(Math.max(start, Math.min(end, baseStart + Math.round((event.clientX - box.left) / box.width * (data.comparison.samples.length - 1)))))
        }}>
          <rect x={plotX(start)} y="0" width={plotX(end) - plotX(start)} height="120" fill="#4daaca" opacity={selectedWindow ? .12 : .025} />
          {[20, 60, 100].map(y => <line key={y} x1="0" y1={y} x2="1000" y2={y} className="plot-grid" />)}
          {data.comparison.regions.map((item, column) => <path key={item.label_id} d={wavePath(data.comparison.zscore.map(row => row[column]), extent)} fill="none" stroke={`rgb(${displayColor(item).join(',')})`} strokeDasharray={column ? '7 4' : undefined} strokeWidth="1.8" vectorEffect="non-scaling-stroke" />)}
          <line x1={fraction * 1000} x2={fraction * 1000} y1="0" y2="120" className="playback-cursor" />
        </svg><div className="plot-axis">{[0, .25, .5, .75, 1].map(t => <span key={t}>{Math.round(baseStart + t * (baseEnd - baseStart)).toString().padStart(3, '0')}</span>)}</div></div>
        <div className="playback-controls"><button onClick={() => setPlaying(value => !value)} aria-label={playing ? '샘플 재생 정지' : '샘플 재생 시작'}>{playing ? '■' : '▶'}</button><input type="range" min={start} max={end} value={cursor} aria-label="재생 샘플" onChange={e => { setPlaying(false); setCursor(Number(e.target.value)) }} /><span>{cursor.toString().padStart(3, '0')}</span></div>
        <div className="window-strip"><button className={windowIndex === null ? 'selected' : ''} onClick={() => chooseWindow(null)}>전체</button><div className="window-bars" aria-label={`${selection?.window ?? Math.min(50, baseEnd - baseStart + 1)}샘플 이동 창 · ${selection?.step ?? Math.min(10, baseEnd - baseStart + 1)}샘플 간격`}>{data.windows.map((window, index) => <button key={window.start_sample} className={windowIndex === index ? 'selected' : ''} onClick={() => chooseWindow(index)} aria-pressed={windowIndex === index} aria-label={`구간 ${window.start_sample}~${window.end_sample}, 상관 ${window.correlation?.toFixed(3) ?? '계산 불가'}`} title={`${window.start_sample}~${window.end_sample} · ${selection?.method === 'spearman' ? 'ρ' : 'r'} ${window.correlation?.toFixed(3) ?? '—'}`}><i style={{ height: `${Math.max(8, Math.abs(window.correlation ?? 0) * 100)}%`, background: window.correlation === null ? '#536570' : window.correlation < 0 ? '#e9ad76' : '#6bbfe3' }} /></button>)}</div></div>
      </> : <div className="stage-wait">계산이 완료되면 파형·구간과 재생 커서를 표시합니다.</div>}
    </div>
    </div>

    <aside className="comparison-panel framed">
      <p className="eyebrow">REGION METRICS</p><h2>영역 분석</h2>
      {data ? <>
        <div className="current-signal" role="group" aria-label={single ? '현재 샘플의 선택 영역 신호' : '현재 샘플의 두 영역 신호'}>
          <div className="current-signal-heading"><span>현재 신호 <small>z-score</small></span><small>SAMPLE {cursor.toString().padStart(3, '0')}</small></div>
          <div className="current-signal-values">{data.comparison.zscore[sampleIndex].map((value, column) => <div key={column} style={roiStyle(data.comparison.regions[column])}><small>{regionLabel(data.comparison.regions[column])}</small><strong>{value.toFixed(2)}</strong></div>)}</div>
        </div>
        <table className="comparison-table"><caption className="sr-only">선택 영역의 구조 수치</caption><thead><tr><th scope="col">지표</th>{data.comparison.regions.map(item => <th key={item.label_id} scope="col">{regionLabel(item)}</th>)}</tr></thead><tbody>
          <tr><th scope="row">두께 <small>mm</small></th>{data.comparison.regions.map(item => <td key={item.label_id}>{item.thickness_mm.toFixed(3)}</td>)}</tr>
          <tr><th scope="row">부피 <small>mm³</small></th>{data.comparison.regions.map(item => <td key={item.label_id}>{item.volume_mm3.toLocaleString()}</td>)}</tr>
        </tbody></table>
        {!single && <div className="stage-correlation"><span>{correlationLabel(start, end, !!selectedWindow)} · {selection?.method === 'spearman' ? 'SPEARMAN ρ' : 'PEARSON r'}</span><strong>{currentCorrelation?.toFixed(3) ?? '—'}</strong></div>}
        <dl className="small-metrics"><dt>분석 구간</dt><dd>{start}~{end}</dd><dt>표시 신호</dt><dd>z-score</dd><dt>파형 공통 축</dt><dd>±{extent.toFixed(2)}</dd></dl>
      </> : <p className="stage-wait">실제 계산 결과를 기다리고 있습니다.</p>}
    </aside>


    <dialog ref={dialog} className="analysis-detail analysis-detail--pair" aria-labelledby="analysis-detail-title" onCancel={() => setDetail(null)} onClose={() => setDetail(null)}>
      <button className="detail-close" aria-label="상세 닫기" onClick={() => setDetail(null)}>×</button>
      {data && detail !== null && (detail === 'mri' ? <><p className="eyebrow">PROVIDED MRI / ACTUAL SLICES</p><h2 id="analysis-detail-title">Axial · Coronal 실제 MRI</h2><div className="detail-mri-pair">{data.planes.map(plane => <figure key={plane.record.orientation}><figcaption>{plane.record.orientation === 'Axial' ? 'Axial · 수평면' : 'Coronal · 관상면'} / {plane.record.slice_index}번</figcaption><SliceCanvas plane={plane} regions={data.comparison.regions} values={data.comparison.zscore[sampleIndex]} label={`확대한 ${plane.record.orientation} 실제 MRI와 영역 마스크`} /></figure>)}</div><p>원본 PNG 방향을 유지합니다. 선택 영역의 색은 모형·파형과 대응합니다. 이미지의 화면 좌우와 해부학적 좌우는 다를 수 있습니다.</p></> : <>
        <p className="eyebrow">REGION DETAIL / LOCAL DATA</p><h2 id="analysis-detail-title">{pairTitle}</h2>
        <div className="roi-image-pair">{data.comparison.regions.map((_, column) => <RegionCard key={column} data={data} column={column} sample={cursor} expanded />)}</div>
        <p>각 영역이 잘 보이는 실제 단면을 확대하며 원본 이미지 방향을 유지합니다.</p>
      </>)}
    </dialog>
  </section>
}
