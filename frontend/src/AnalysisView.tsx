import { useEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { regionLabel } from './api.ts'
import type { Region } from './api.ts'
import { advanceSample } from './analysisModel.ts'
import { wavePath } from './model.ts'
import { loadStage } from './stageData.ts'
import type { StageData, StageSelection } from './stageData.ts'
import BrainStage, { SliceCanvas } from './BrainStage.tsx'

const roiStyle = (region: Region) => ({ '--roi-color': `rgb(${region.color_rgb.join(',')})` } as CSSProperties)

function RegionCard({ data, column, sample, onDetail }: { data: StageData; column: number; sample: number; onDetail: () => void }) {
  const region = data.comparison.regions[column]
  const plane = [...data.planes].sort((a, b) => (b.record.pixel_counts[String(region.label_id)] ?? 0) - (a.record.pixel_counts[String(region.label_id)] ?? 0))[0]
  const available = column ? plane.cloud.boundsB : plane.cloud.boundsA
  return <button className="region-card" style={roiStyle(region)} onClick={onDetail} aria-label={`${regionLabel(region)} 상세 보기`}>
    <div className="region-card-image">{available ? <SliceCanvas plane={plane} region={column} regions={data.comparison.regions} label={`${regionLabel(region)} 실제 단면 확대`} /> : <span>이 단면에는 영역 없음</span>}</div>
    <div><small>{column ? 'REGION B' : 'REGION A'} · ROI {region.label_id.toString().padStart(2, '0')}</small><h3>{regionLabel(region)}</h3><span className="sample-value">z {(data.comparison.zscore[sample - 1]?.[column] ?? 0).toFixed(2)}</span></div>
    <span className="card-detail-link">상세 ↗</span>
  </button>
}

export default function AnalysisView({ regions, version, active, blocked, reduced, onBusyChange }: {
  regions: Region[]; version: string; active: boolean; blocked: boolean; reduced: boolean; onBusyChange: (value: boolean) => void;
}) {
  const [selection, setSelection] = useState<StageSelection | null>(null)
  const [data, setData] = useState<StageData | null>(null)
  const [phase, setPhase] = useState('대응 영역 관계 검색')
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [cursor, setCursor] = useState(1)
  const [playing, setPlaying] = useState(false)
  const [visible, setVisible] = useState(() => !document.hidden)
  const [windowIndex, setWindowIndex] = useState<number | null>(null)
  const [detail, setDetail] = useState<0 | 1 | 'mri' | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const autoPlay = useRef(!reduced)
  useEffect(() => { autoPlay.current = !reduced; if (reduced) setPlaying(false) }, [reduced])

  useEffect(() => {
    const controller = new AbortController()
    onBusyChange(true); setData(null); setError(''); setPlaying(false); setDetail(null)
    loadStage(regions, version, selection, controller.signal, label => { if (!controller.signal.aborted) setPhase(label) })
      .then(result => {
        if (controller.signal.aborted) return
        setData(result); setCursor(1); setWindowIndex(null); setPhase('로컬 분석 완료'); setPlaying(autoPlay.current && !document.hidden)
      }).catch(reason => {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : '로컬 분석을 완료하지 못했습니다.')
      }).finally(() => { if (!controller.signal.aborted) onBusyChange(false) })
    return () => { controller.abort(); onBusyChange(false) }
  }, [regions, version, selection, attempt, onBusyChange])

  const selectedWindow = windowIndex === null ? null : data?.windows[windowIndex]
  const start = selectedWindow?.start_sample ?? 1, end = selectedWindow?.end_sample ?? data?.comparison.samples.length ?? 200
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

  const showDetail = (value: 0 | 1 | 'mri') => { setPlaying(false); setDetail(value) }
  const chooseWindow = (index: number | null) => {
    setPlaying(false); setWindowIndex(index); setCursor(index === null ? 1 : data!.windows[index].start_sample)
  }
  const region = data?.comparison.regions[0] ?? regions.find(item => item.label_id === selection?.region)
  const direction = data?.center.record.orientation ?? selection?.orientation
  const extent = data ? Math.max(3, ...data.comparison.zscore.flat().map(Math.abs)) : 3
  const fraction = data ? (cursor - 1) / Math.max(1, data.comparison.samples.length - 1) : 0
  const currentCorrelation = selectedWindow ? selectedWindow.correlation : data?.comparison.correlation
  const detailPlane = data && typeof detail === 'number' ? [...data.planes].sort((a, b) =>
    (b.record.pixel_counts[String(data.comparison.regions[detail].label_id)] ?? 0) - (a.record.pixel_counts[String(data.comparison.regions[detail].label_id)] ?? 0))[0] : data?.center

  return <section className={`analysis-workspace analysis-workspace--expanded${data ? ' stage-complete' : ''}`} aria-label="뇌 데이터 탐색" aria-busy={!data && !error}>
    <aside className="selection-panel framed">
      <p className="eyebrow">01 / SELECTED REGION</p><h2>두 영역의 기록</h2>
      {data ? <>
        <RegionCard data={data} column={0} sample={cursor} onDetail={() => showDetail(0)} />
        <dl className="stage-structure"><dt>평균 두께</dt><dd>{data.comparison.regions[0].thickness_mm.toFixed(3)} mm</dd><dt>회백질 부피</dt><dd>{data.comparison.regions[0].volume_mm3.toLocaleString()} mm³</dd></dl>
        <p className="stage-origin">{data.automatic ? '대응 영역 중 상관이 가장 높은 쌍' : '직접 선택한 영역과 반대쪽 대응 영역'}</p>
      </> : <p className="stage-wait">{error ? '분석을 다시 실행해 주세요.' : phase}</p>}
      <details className="manual-selection"><summary aria-disabled={!data && !error}>직접 변경</summary>
        <div className="selection-controls"><label htmlFor="region-select">선택 영역</label>
          <select id="region-select" value={region?.label_id ?? regions[0].label_id} disabled={!data && !error} onChange={e => setSelection({ region: Number(e.target.value) })}>{regions.map(item => <option key={item.label_id} value={item.label_id}>{regionLabel(item)}</option>)}</select>
          <label htmlFor="orientation-select">단면 방향</label><select id="orientation-select" value={direction ?? 'Axial'} disabled={!data && !error} onChange={e => setSelection({ region: region?.label_id ?? regions[0].label_id, orientation: e.target.value as 'Axial' | 'Coronal' })}><option value="Axial">Axial · 수평면</option><option value="Coronal">Coronal · 관상면</option></select>
          <p>영역을 바꾸면 두 영역이 잘 보이는 방향·단면을 자동 선택합니다.</p>
        </div>
      </details>
    </aside>

    <div className="brain-panel framed">
      <div className="panel-heading"><span className="eyebrow">02 / NEURAL RELATION STAGE</span><span className="quiet">{data ? `${direction?.toUpperCase()} / ${data.center.record.slice_index.toString().padStart(3, '0')}` : 'LOCAL ANALYSIS'}</span></div>
      {error ? <div className="empty-state" role="alert"><p>{error}</p><button onClick={() => setAttempt(value => value + 1)}>분석 다시 시도</button></div>
        : !data ? <div className="empty-state" role="status"><span className="loading-mark" /><strong>{phase}</strong><small>실제 로컬 데이터 처리 중</small></div>
        : <div className="brain-stage-body">
          <BrainStage data={data} sample={cursor} active={active && !blocked && visible} reduced={reduced} onRegion={column => showDetail(column as 0 | 1)} />
          <button className="mri-inset" onClick={() => showDetail('mri')} aria-label="실제 MRI 단면 확대"><SliceCanvas plane={data.center} regions={data.comparison.regions} label="실제 MRI와 선택 영역 마스크" /><span>실제 MRI ↗</span></button>
          <span className="stage-sample">SAMPLE <b>{cursor.toString().padStart(3, '0')}</b></span>
        </div>}
      <div className="brain-caption"><span className="live-dot" />제공 단면의 공간 연출<span className="quiet">깊이·관계선은 표시용 · 정밀 3D 복원 아님</span></div>
    </div>

    <aside className="comparison-panel framed">
      <p className="eyebrow">03 / RELATION ANALYSIS</p><h2>함께 변하는 정도</h2>
      {data ? <>
        <RegionCard data={data} column={1} sample={cursor} onDetail={() => showDetail(1)} />
        <div className="stage-correlation"><span>{selectedWindow ? '선택 구간' : '전체 구간'} · PEARSON r</span><strong>{currentCorrelation?.toFixed(3) ?? '—'}</strong></div>
        <dl className="small-metrics"><dt>분석 구간</dt><dd>{start}~{end}</dd><dt>표시 신호</dt><dd>z-score</dd><dt>파형 공통 축</dt><dd>±{extent.toFixed(2)}</dd></dl>
        <p className="stage-disclaimer">상관과 관계선은 직접 신경 연결·인과·개인의 능력을 뜻하지 않습니다.</p>
      </> : <p className="stage-wait">실제 계산 결과를 기다리고 있습니다.</p>}
    </aside>

    <div className="signal-panel framed">
      <div className="panel-heading"><span className="eyebrow">BOLD / TWO SIGNALS</span><span className="quiet">SAMPLE 1~200 · 초 단위 아님</span></div>
      {data ? <>
        <div className="stage-chart-wrap"><svg viewBox="0 0 1000 120" preserveAspectRatio="none" role="img" aria-label="두 영역의 실제 표준화 BOLD 파형" onPointerDown={event => {
          const box = event.currentTarget.getBoundingClientRect()
          setPlaying(false); setCursor(Math.max(start, Math.min(end, 1 + Math.round((event.clientX - box.left) / box.width * (data.comparison.samples.length - 1)))))
        }}>
          <rect x={(start - 1) / 199 * 1000} y="0" width={(end - start) / 199 * 1000} height="120" fill="#4daaca" opacity={selectedWindow ? .12 : .025} />
          {[20, 60, 100].map(y => <line key={y} x1="0" y1={y} x2="1000" y2={y} className="plot-grid" />)}
          {[0, 1].map(column => <path key={column} d={wavePath(data.comparison.zscore.map(row => row[column]), extent)} fill="none" stroke={`rgb(${data.comparison.regions[column].color_rgb.join(',')})`} strokeDasharray={column ? '7 4' : undefined} strokeWidth="1.8" vectorEffect="non-scaling-stroke" />)}
          <line x1={fraction * 1000} x2={fraction * 1000} y1="0" y2="120" className="playback-cursor" />
        </svg><div className="plot-axis"><span>001</span><span>050</span><span>100</span><span>150</span><span>200</span></div></div>
        <div className="playback-controls"><button onClick={() => setPlaying(value => !value)} aria-label={playing ? '샘플 재생 일시정지' : '샘플 재생 시작'}>{playing ? 'Ⅱ' : '▶'}</button><input type="range" min={start} max={end} value={cursor} aria-label="재생 샘플" onChange={e => { setPlaying(false); setCursor(Number(e.target.value)) }} /><span>{cursor.toString().padStart(3, '0')}</span><small>10 samples/s · 연출 속도</small></div>
        <div className="window-strip"><button className={windowIndex === null ? 'selected' : ''} onClick={() => chooseWindow(null)}>전체</button><div className="window-bars" aria-label="50샘플 이동 창 · 10샘플 간격">{data.windows.map((window, index) => <button key={window.start_sample} className={windowIndex === index ? 'selected' : ''} onClick={() => chooseWindow(index)} aria-pressed={windowIndex === index} aria-label={`구간 ${window.start_sample}~${window.end_sample}, 상관 ${window.correlation?.toFixed(3) ?? '계산 불가'}`} title={`${window.start_sample}~${window.end_sample} · r ${window.correlation?.toFixed(3) ?? '—'}`}><i style={{ height: `${Math.max(8, Math.abs(window.correlation ?? 0) * 100)}%`, background: window.correlation === null ? '#536570' : window.correlation < 0 ? '#e9ad76' : '#6bbfe3' }} /></button>)}</div><small>50점 창 / 10점 간격</small></div>
      </> : <div className="stage-wait">계산이 완료되면 파형·구간과 재생 커서를 표시합니다.</div>}
    </div>

    <dialog ref={dialog} className="analysis-detail" aria-labelledby="analysis-detail-title" onCancel={() => setDetail(null)} onClose={() => setDetail(null)}>
      <button className="detail-close" aria-label="상세 닫기" onClick={() => setDetail(null)}>×</button>
      {data && detail !== null && (detail === 'mri' ? <><p className="eyebrow">PROVIDED MRI / ACTUAL SLICE</p><h2 id="analysis-detail-title">{direction} · {data.center.record.slice_index}번 단면</h2><SliceCanvas plane={data.center} regions={data.comparison.regions} label="확대한 실제 MRI와 영역 마스크" /><p>원래 이미지 방향을 유지합니다. 공간 무대의 깊이는 이 단면에 부여한 연출입니다.</p></> : <>
        <p className="eyebrow">REGION DETAIL / LOCAL DATA</p><h2 id="analysis-detail-title">{regionLabel(data.comparison.regions[detail])}</h2>
        {detailPlane && (detail === 0 ? detailPlane.cloud.boundsA : detailPlane.cloud.boundsB) ? <SliceCanvas plane={detailPlane!} regions={data.comparison.regions} region={detail} label="선택 영역 실제 단면 확대" /> : <p>이 단면에는 영역이 없습니다.</p>}
        <dl><dt>평균 피질 두께</dt><dd>{data.comparison.regions[detail].thickness_mm.toFixed(3)} mm</dd><dt>회백질 부피</dt><dd>{data.comparison.regions[detail].volume_mm3.toLocaleString()} mm³</dd><dt>현재 샘플</dt><dd>{cursor} / z {data.comparison.zscore[cursor - 1][detail].toFixed(3)}</dd><dt>전체 기록 최댓값 / 최솟값</dt><dd>{Math.max(...data.comparison.zscore.map(row => row[detail])).toFixed(3)} / {Math.min(...data.comparison.zscore.map(row => row[detail])).toFixed(3)}</dd></dl><p>z-score는 전체 기록 기준입니다. 구조·신호 값으로 지능·성격·학습량을 판정하지 않습니다.</p>
      </>)}
    </dialog>
  </section>
}
