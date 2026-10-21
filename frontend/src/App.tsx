import { useEffect, useState } from 'react'
import CoreScene from './CoreScene.tsx'
import AnalysisView from './AnalysisView.tsx'
import { api } from './api.ts'
import type { Region, Summary } from './api.ts'
import { INTRO, introStage, toggleComposer } from './model.ts'
import type { ComposerPanel, IntroStage } from './model.ts'
import { useAudioPreview } from './audio.ts'
import { Composer, Icon } from './Interface.tsx'

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const media = matchMedia('(prefers-reduced-motion: reduce)')
    const changed = () => setReduced(media.matches)
    media.addEventListener('change', changed)
    return () => media.removeEventListener('change', changed)
  }, [])
  return reduced
}

export default function App() {
  const reduced = useReducedMotion()
  const [stage, setStage] = useState<IntroStage>(() => introStage(0, reduced))
  const [replay, setReplay] = useState(0)
  const [skipped, setSkipped] = useState(false)
  const [view, setView] = useState<'home' | 'analysis'>('home')
  const [explored, setExplored] = useState(false)
  const [panel, setPanel] = useState<ComposerPanel>('text')
  const [draft, setDraft] = useState('')
  const [connection, setConnection] = useState<'loading' | 'ready' | 'error'>('loading')
  const [data, setData] = useState<{ regions: Region[]; summary: Summary } | null>(null)
  const [connectionError, setConnectionError] = useState('')
  const [retry, setRetry] = useState(0)
  const [analysisBusy, setAnalysisBusy] = useState(false)
  const audio = useAudioPreview()

  useEffect(() => {
    setStage(introStage(0, reduced || skipped))
    if (reduced || skipped) return
    const timers = Object.values(INTRO).map(time => setTimeout(() => setStage(introStage(time)), time))
    return () => timers.forEach(clearTimeout)
  }, [reduced, replay, skipped])

  useEffect(() => {
    const controller = new AbortController()
    setConnection('loading')
    setConnectionError('')
    Promise.all([
      api<{ status: string; dataset_version: string }>('/api/health', controller.signal),
      api<Summary>('/api/dataset', controller.signal),
      api<{ dataset_version: string; regions: Region[] }>('/api/regions', controller.signal),
    ]).then(([health, summary, regions]) => {
      if (controller.signal.aborted) return
      if (health.status !== 'ok' || health.dataset_version !== summary.dataset_version || regions.dataset_version !== summary.dataset_version) throw new Error('서버의 데이터 버전이 일치하지 않습니다.')
      setData({ regions: regions.regions, summary })
      setConnection('ready')
    }).catch(reason => {
      if (!controller.signal.aborted) {
        setConnection('error')
        setConnectionError(reason instanceof Error ? reason.message : '서버 연결을 확인해 주세요.')
      }
    })
    return () => controller.abort()
  }, [retry])

  const explore = () => { audio.stop(); setExplored(true); setPanel(null); setView('analysis') }
  const home = () => { audio.stop(); setPanel('text'); setView('home') }
  const restart = () => { home(); setSkipped(false); setReplay(v => v + 1) }
  const ready = stage === 'ready'
  const locked = !ready || audio.active || (view === 'analysis' && analysisBusy)

  return <div className={`app app--${stage} app--${view}${panel ? ' app--composer-open' : ''}${audio.active ? ' app--preview' : ''}`}>
    <div className="background-grid" aria-hidden="true" />
    <header className="interface-header">
      <div className="brand"><h1>NERVIS</h1><span>NEURAL DATA EXPLORER</span></div>
      <div className="header-center"><i />INTERACTIVE NEURAL INTERFACE<i /></div>
      <div className="connection-chip" aria-live="polite"><span className={`live-dot ${connection}`} />
        {audio.active ? '오디오 미리보기 · AI 연결 전' : view === 'analysis' && analysisBusy ? '로컬 분석 중 · AI 연결 전' : 'NERVIS 대기 · AI 연결 전'}</div>
    </header>

    {(stage === 'title' || stage === 'dock') && <div className="intro-caption"><span>AN INTERFACE TO EXPLORE</span><p>기록 속의 관계를 발견하다</p></div>}
    {!ready && <button className="skip-intro" onClick={() => setSkipped(true)}>인트로 건너뛰기 <span>↗</span></button>}

    <div className="core-stage" aria-hidden="true">
      <div className="core-aura" />
      <div className="orbit-guide"><span className="orbit-notch n1" /><span className="orbit-notch n2" /><span className="orbit-notch n3" /></div>
      {(stage === 'core' || ready) && <CoreScene level={audio.level} reduced={reduced} />}
      <div className="core-crosshair ch-left" /><div className="core-crosshair ch-right" />
    </div>

    <main className={`screen-content${ready ? ' is-ready' : ''}`} inert={!ready}>
      <section className="home-screen" hidden={view !== 'home'} aria-label="NERVIS 대화 홈">
        <div className="core-caption"><span className="live-dot" />{audio.active ? 'AUDIO-REACTIVE PREVIEW' : 'NERVIS / STANDBY'}<small>PROCEDURAL CORE · LOCAL RENDER</small></div>
      </section>

      {explored && data && <div className="analysis-container" inert={audio.active} hidden={view !== 'analysis'}>
        <AnalysisView regions={data.regions} version={data.summary.dataset_version} active={view === 'analysis'} blocked={audio.active} reduced={reduced} onBusyChange={setAnalysisBusy} />
      </div>}
    </main>

    <div className={`common-interface${ready ? ' is-ready' : ''}`} inert={!ready}>
      <Composer panel={panel} draft={draft} onDraft={setDraft} closable={view === 'analysis' || panel === 'voice'} locked={locked}
        onToggle={target => setPanel(current => toggleComposer(current, target, view))}
        onClose={() => setPanel(view === 'home' ? 'text' : null)} />
      <footer className="shell-footer">
        <div className="shell-actions"><span>INTERFACE / 02</span>
          <button className="local-view-button" disabled={locked || (view === 'home' && connection !== 'ready')} onClick={view === 'home' ? explore : home}>
            {view === 'home' ? '분석 화면 미리보기 ↗' : '대화 홈으로 ↖'}</button>
        </div>
        <button className={`sound-preview${audio.active ? ' active' : ''}`} disabled={!ready || (view === 'analysis' && analysisBusy)} onClick={() => audio.active ? audio.stop() : void audio.play()}>
          <Icon name="sound" />{audio.active ? '미리보기 중지' : '코어 음량 반응 미리보기'}<small>로컬 합성음 · AI 음성 아님</small>
        </button>
        <button className="replay-button" onClick={restart} disabled={locked}>시작 연출 다시 보기 ↗</button>
      </footer>
      {connection === 'error' && <div className="shell-error" role="alert"><p>{connectionError}</p><button onClick={() => setRetry(v => v + 1)}>서버 연결 다시 확인</button></div>}
    </div>
    {audio.error && <p className="audio-error" role="alert">{audio.error}</p>}
  </div>
}
