import { useCallback, useEffect, useRef, useState } from 'react'
import CoreScene from './CoreScene.tsx'
import AnalysisView from './AnalysisView.tsx'
import { api, ApiError } from './api.ts'
import type { Region, Summary } from './api.ts'
import { INTRO, introStage, toggleComposer } from './model.ts'
import type { ComposerPanel, IntroStage } from './model.ts'
import { useAudioPreview } from './audio.ts'
import { Composer, Icon } from './Interface.tsx'
import ConversationPanel from './ConversationPanel.tsx'
import { checkedReply, viewSelection, pending, aiErrorMessage } from './conversation.ts'
import type { AIStatus, AIReply, CommandPhase, ViewContext, ViewRequest } from './conversation.ts'
import type { StageSelection } from './stageData.ts'

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
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null)
  const [phase, setPhase] = useState<CommandPhase>('idle')
  const [reply, setReply] = useState<AIReply | null>(null)
  const [command, setCommand] = useState('')
  const [requestError, setRequestError] = useState('')
  const [stageRequest, setStageRequest] = useState<ViewRequest | null>(null)
  const context = useRef<ViewContext>({ selected_region_ids: [], start: 1, end: 200 })
  const flight = useRef(false), expectedStage = useRef<number | null>(null), sequence = useRef(0)
  const controller = useRef<AbortController | null>(null)
  const mounted = useRef(true)
  const refreshAI = useCallback(async () => {
    try {
      const value = await api<AIStatus>('/api/ai/status', new AbortController().signal)
      if (mounted.current) setAIStatus(value)
    } catch { if (mounted.current) setAIStatus(null) }
  }, [])
  useEffect(() => {
    mounted.current = true; void refreshAI()
    const focus = () => { void refreshAI() }
    window.addEventListener('focus', focus)
    return () => { mounted.current = false; controller.current?.abort(); window.removeEventListener('focus', focus) }
  }, [refreshAI])
  useEffect(() => {
    if (!aiStatus?.busy) return
    const timer = setInterval(() => { void refreshAI() }, 1500)
    return () => clearInterval(timer)
  }, [aiStatus?.busy, refreshAI])
  const onContext = useCallback((value: ViewContext) => { context.current = value }, [])
  const onApplied = useCallback((id: number, error?: string) => {
    if (expectedStage.current !== id) return
    expectedStage.current = error ? id : null; flight.current = false
    setRequestError(error ? `계산 결과는 받았지만 화면 적용에 실패했습니다: ${error}` : '')
    setPhase(error ? 'error' : 'complete')
  }, [])
  const onStageBusy = useCallback((busy: boolean) => {
    setAnalysisBusy(busy)
    if (busy && expectedStage.current !== null) {
      flight.current = true; setRequestError(''); setPhase('applying')
    }
  }, [])
  const applySelection = (selection: StageSelection) => {
    const id = ++sequence.current
    expectedStage.current = id; flight.current = true
    setStageRequest({ id, selection }); setExplored(true); setView('analysis'); setPanel(null); setPhase('applying')
  }
  const send = async () => {
    if (flight.current || locked || !aiStatus?.enabled || aiStatus.busy || !draft.trim() || !data) return
    flight.current = true; expectedStage.current = null
    const submitted = draft.trim(), current = new AbortController()
    controller.current = current
    setCommand(submitted); setReply(null); setRequestError(''); setPhase('requesting')
    const timeout = setTimeout(() => current.abort(), 70000)
    try {
      const response = checkedReply(await api<AIReply>('/api/ai/chat', current.signal,
        { command: submitted, context: context.current }), data.summary.dataset_version)
      if (!mounted.current) return
      const selection = viewSelection(response)
      setReply(response); setDraft('')
      if (selection) applySelection(selection)
      else { flight.current = false; setPhase('complete') }
    } catch (error) {
      if (!mounted.current) return
      setRequestError(error instanceof ApiError ? aiErrorMessage(error.code) : error instanceof DOMException && error.name === 'AbortError'
        ? '응답 대기 시간이 지났습니다. 서버 처리가 계속될 수 있어 자동 재전송하지 않습니다.'
        : error instanceof Error ? error.message : '요청을 완료하지 못했습니다.')
      setPhase('error'); flight.current = false
    } finally {
      clearTimeout(timeout); controller.current = null
      if (mounted.current) { setAIStatus(null); void refreshAI() }
    }
  }
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
  const locked = !ready || audio.active || pending(phase) || (view === 'analysis' && analysisBusy)
  const canSend = !locked && connection === 'ready' && !!aiStatus?.enabled && !aiStatus.busy
  const inputStatus = !aiStatus ? 'AI 서버 상태를 확인해 주세요. 분석 자료·비밀값은 입력하지 마세요.' : aiStatus.busy ? '서버가 이전 요청을 처리 중입니다.' : !aiStatus.enabled ? '텍스트 연결 준비됨 · 외부 AI 호출 꺼짐 또는 예산 소진' : `텍스트 명령 입력 · Shift+Enter 줄바꿈 · 남은 호출 ${aiStatus.remaining_process_requests}회`

  return <div className={`app app--${stage} app--${view}${panel ? ' app--composer-open' : ''}${audio.active ? ' app--preview' : ''}`}>
    <div className="background-grid" aria-hidden="true" />
    <header className="interface-header">
      <div className="brand"><h1>NERVIS</h1><span>NEURAL DATA EXPLORER</span></div>
      <div className="header-center"><i />INTERACTIVE NEURAL INTERFACE<i /></div>
      <div className="connection-chip" aria-live="polite"><span className={`live-dot ${connection}`} />
        {audio.active ? '로컬 오디오 미리보기' : phase === 'requesting' ? 'NERVIS 요청 처리 중' : phase === 'applying' || analysisBusy ? '분석 화면 준비 중' : aiStatus?.busy ? '서버 요청 처리 중' : aiStatus?.enabled ? `텍스트 연결 · ${aiStatus.model}` : '텍스트 연결 · AI 호출 꺼짐'}</div>
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

      {explored && data && <div className="analysis-container" inert={audio.active || pending(phase)} hidden={view !== 'analysis'}>
        <AnalysisView key={stageRequest?.id ?? 'preview'} request={stageRequest} onApplied={onApplied} onContext={onContext} regions={data.regions} version={data.summary.dataset_version} active={view === 'analysis'} blocked={audio.active || phase === 'requesting'} reduced={reduced} onBusyChange={onStageBusy} />
      </div>}
    </main>

    <div className={`common-interface${ready ? ' is-ready' : ''}`} inert={!ready}>
      <ConversationPanel phase={phase} command={command} reply={reply} error={requestError} regions={data?.regions ?? []} locked={locked}
        onSelect={selection => { if (!flight.current && !locked) { setRequestError(''); applySelection(selection) } }}
        onClose={() => { if (!flight.current) { expectedStage.current = null; setPhase('idle'); setReply(null); setRequestError('') } }} />
      <Composer canSend={canSend} status={inputStatus} onSend={() => { void send() }} panel={panel} draft={draft} onDraft={setDraft} closable={view === 'analysis' || panel === 'voice'} locked={locked}
        onToggle={target => setPanel(current => toggleComposer(current, target, view))}
        onClose={() => setPanel(view === 'home' ? 'text' : null)} />
      <footer className="shell-footer">
        <div className="shell-actions"><span>INTERFACE / 02</span>
          <button className="local-view-button" disabled={locked || (view === 'home' && connection !== 'ready')} onClick={view === 'home' ? explore : home}>
            {view === 'home' ? '분석 화면 미리보기 ↗' : '대화 홈으로 ↖'}</button>
        </div>
        <button className={`sound-preview${audio.active ? ' active' : ''}`} disabled={pending(phase) || !ready || (view === 'analysis' && analysisBusy)} onClick={() => audio.active ? audio.stop() : void audio.play()}>
          <Icon name="sound" />{audio.active ? '미리보기 중지' : '코어 음량 반응 미리보기'}<small>로컬 합성음 · AI 음성 아님</small>
        </button>
        <button className="replay-button" onClick={restart} disabled={locked}>시작 연출 다시 보기 ↗</button>
      </footer>
      {(!aiStatus || !aiStatus.enabled) && ready && <button className="ai-status-refresh" disabled={pending(phase)} onClick={() => { void refreshAI() }}>AI 설정 상태 확인</button>}
      {connection === 'error' && <div className="shell-error" role="alert"><p>{connectionError}</p><button onClick={() => setRetry(v => v + 1)}>서버 연결 다시 확인</button></div>}
    </div>
    {audio.error && <p className="audio-error" role="alert">{audio.error}</p>}
  </div>
}
