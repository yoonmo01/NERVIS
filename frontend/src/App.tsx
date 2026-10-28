import { useCallback, useEffect, useRef, useState } from 'react'
import CoreScene from './CoreScene.tsx'
import ConversationHistory from './ConversationHistory.tsx'
import { useConversation } from './useConversation.ts'
import { isTaskTool } from './tasks.ts'
import AnalysisView from './AnalysisView.tsx'
import BriefingCards from './BriefingCards.tsx'
import { briefingFromResults, previewKind } from './briefing.ts'
import type { Briefing } from './briefing.ts'
import { api, ApiError } from './api.ts'
import type { Region, Summary } from './api.ts'
import { INTRO, introStage, toggleComposer } from './model.ts'
import type { ComposerPanel, IntroStage } from './model.ts'
import { useAudioPreview } from './audio.ts'
import { useSpeech } from './useSpeech.ts'
import { Composer, Icon } from './Interface.tsx'
import ConversationPanel, { CalculationResults } from './ConversationPanel.tsx'
import { checkedReply, viewSelection, pending, aiErrorMessage, interfaceState } from './conversation.ts'
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
  const conversation = useConversation()
  const [historyOpen, setHistoryOpen] = useState(false)
  const [stage, setStage] = useState<IntroStage>(() => introStage(0, reduced))
  const [replay, setReplay] = useState(0)
  const [skipped, setSkipped] = useState(false)
  const [view, setView] = useState<'home' | 'analysis'>('home')
  const [explored, setExplored] = useState(false)
  const [panel, setPanel] = useState<ComposerPanel>('text')
  const [draft, setDraft] = useState('')
  const [voiceActive, setVoiceActive] = useState(false)
  const [briefingPreview, setBriefingPreview] = useState(false)
  const [briefingCards, setBriefingCards] = useState<{ id: number; value: Briefing } | null>(null)
  const cardsFlight = useRef(false)
  const onCardsReady = useCallback(() => {
    if (!cardsFlight.current) return
    cardsFlight.current = false; flight.current = false; setPhase('complete')
  }, [])
  const [connection, setConnection] = useState<'loading' | 'ready' | 'error'>('loading')
  const [data, setData] = useState<{ regions: Region[]; summary: Summary } | null>(null)
  const [connectionError, setConnectionError] = useState('')
  const [retry, setRetry] = useState(0)
  const [analysisBusy, setAnalysisBusy] = useState(false)
  const [aiStatus, setAIStatus] = useState<AIStatus | null>(null)
  const [phase, setPhase] = useState<CommandPhase>('idle')
  const [reply, setReply] = useState<AIReply | null>(null)
  const [resultOpen, setResultOpen] = useState(true)
  const [analysisTab, setAnalysisTab] = useState<'mri' | 'response' | 'calculations'>('mri')
  const [command, setCommand] = useState('')
  const [requestError, setRequestError] = useState('')
  const [stageRequest, setStageRequest] = useState<ViewRequest | null>(null)
  const context = useRef<ViewContext>({ selected_region_ids: [], start: 1, end: 200 })
  const restoredSession = useRef<string | null>(null)
  useEffect(() => {
    if (conversation.value && restoredSession.current !== conversation.value.id) {
      restoredSession.current = conversation.value.id
      if (conversation.value.state.context) context.current = conversation.value.state.context
    }
  }, [conversation.value])
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
    if (error) {
      speech.stop()
      void speech.play(`계산 결과는 받았지만 화면 적용에 실패했습니다: ${error}`)
    }
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
    if (flight.current || locked || voiceActive || (!briefingPreview && (!aiStatus?.enabled || aiStatus.busy)) || !draft.trim() || !data) return
    flight.current = true; expectedStage.current = null
    speech.prepare()
    const submitted = draft.trim(), current = new AbortController()
    controller.current = current
    setCommand(submitted); setReply(null); setRequestError(''); setPhase('requesting'); setResultOpen(true); setAnalysisTab('response')
    setBriefingCards(null); cardsFlight.current = false
    const timeout = setTimeout(() => current.abort(), 70000)
    try {
      let packet: AIReply
      if (briefingPreview) {
        const kind = previewKind(submitted)
        if (!kind) throw new Error('더미 미리보기에서는 “오늘 할 일 알려줘” 또는 “오늘 날씨 알려줘”를 입력해 주세요. 분석은 미리보기를 끄고 요청하세요.')
        const value = await api<Briefing>('/api/briefing/preview', current.signal)
        packet = { status: 'ok', warning: null, model_acknowledgement: kind === 'weather' ? '날씨 카드의 더미 미리보기입니다.' : '더미 브리핑 미리보기입니다. 날씨, 오늘 수업과 해야 할 일을 순서대로 정리했습니다.',
          results: [{ result_id: `preview-${++sequence.current}`, tool: kind === 'briefing' ? 'get_daily_briefing' : 'get_weather', parameters: {},
            data: kind === 'briefing' ? value as unknown as Record<string, unknown> : { ...value.weather, kind: 'weather', preview: true } }] }
      } else {
        const sessionId = await conversation.ensure()
        packet = await api<AIReply>('/api/ai/chat', current.signal, { command: submitted, context: context.current, session_id: sessionId, request_id: crypto.randomUUID() })
      }
      const response = checkedReply(packet, data.summary.dataset_version)
      if (!mounted.current) return
      const selection = viewSelection(response)
      const briefing = briefingFromResults(response.results)
      setReply(response); setDraft('')
      void speech.play(response.model_acknowledgement?.trim() || '요청 결과를 화면에서 확인해 주세요.')
      if (selection) applySelection(selection)
      else if (response.results.some(result => isTaskTool(result.tool))) { setView('home'); setPanel('text'); setPhase('complete'); flight.current = false }
      else if (briefing) {
        setBriefingCards({ id: ++sequence.current, value: briefing }); cardsFlight.current = true
        setView('home'); setPanel('text'); setPhase('applying')
      }
      else { flight.current = false; setPhase('complete') }
    } catch (error) {
      if (!mounted.current) return
      const message = error instanceof ApiError ? aiErrorMessage(error.code) : error instanceof DOMException && error.name === 'AbortError'
        ? '응답 대기 시간이 지났습니다. 서버 처리가 계속될 수 있어 자동 재전송하지 않습니다.'
        : error instanceof Error ? error.message : '요청을 완료하지 못했습니다.'
      setRequestError(message); void speech.play(message)
      setPhase('error'); flight.current = false
    } finally {
      clearTimeout(timeout); controller.current = null
      if (mounted.current) { void refreshAI(); if (!briefingPreview) { void conversation.reload(); if (historyOpen) void conversation.loadSessions() } }
    }
  }
  const resetConversationView = () => {
    setReply(null); setCommand(''); setDraft(''); setPhase('idle'); setRequestError('')
    setBriefingCards(null); setStageRequest(null); setExplored(false); setView('home'); setPanel('text')
  }
  const newConversation = () => {
    if (flight.current || locked || voiceActive) return
    conversation.startNew()
    context.current = { selected_region_ids: [], start: 1, end: 200 }
    resetConversationView(); setHistoryOpen(false)
  }
  const switchConversation = async (id: string) => {
    if (flight.current || locked || voiceActive || conversation.loading) return
    const selected = await conversation.reload(id)
    if (!selected) return
    context.current = selected.state.context ?? { selected_region_ids: [], start: 1, end: 200 }
    resetConversationView()
  }
  const audio = useAudioPreview()
  const speech = useSpeech()

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
  const locked = !ready || audio.active || speech.active || pending(phase) || (view === 'analysis' && analysisBusy)
  const canSend = !locked && (briefingPreview || (!conversation.loading && !conversation.error)) && connection === 'ready' && (briefingPreview || (!!aiStatus?.enabled && !aiStatus.busy))
  const inputStatus = !briefingPreview && conversation.loading ? '대화 기록을 불러오는 중입니다.' : !briefingPreview && conversation.error ? conversation.error : briefingPreview ? '더미 미리보기 · “오늘 할 일 알려줘” · AI 호출·DB 저장 없음' : !aiStatus ? 'AI 서버 연결을 확인해 주세요.' : aiStatus.busy ? '이전 요청을 처리 중입니다.' : !aiStatus.enabled ? 'AI가 비활성 상태입니다. 서버 설정을 확인해 주세요.' : ''
  const corePhase = phase === 'complete' && reply?.status === 'partial' ? 'error' : phase
  const coreState = speech.active ? speech.phase === 'speaking' ? 'speaking' : 'processing'
    : interfaceState(corePhase !== 'error' && corePhase !== 'requesting' && view === 'analysis' && analysisBusy ? 'applying' : corePhase, connection !== 'error', !!aiStatus?.enabled, !!aiStatus?.busy, audio.active)
  const stateLabels = { standby: 'STANDBY', processing: 'PROCESSING', analyzing: 'ANALYZING', error: 'ERROR', paused: 'PAUSED', preview: 'AUDIO PREVIEW', speaking: 'SPEAKING' }
  const selectResult = (selection: StageSelection) => { if (!flight.current && !locked) { setRequestError(''); applySelection(selection) } }
  const resultPanel = phase === 'idle' ? null : <ConversationPanel phase={phase} command={command} reply={reply} error={requestError} regions={data?.regions ?? []} locked={locked} docked={view === 'analysis'}
    onSelect={selectResult}
    onClose={() => { if (!flight.current) setResultOpen(false) }} />
  const calculationReply = reply ? { ...reply, results: reply.results.filter(r => r.tool !== 'get_daily_briefing' && r.tool !== 'get_weather' && !isTaskTool(r.tool)) } : null
  const calculations = calculationReply?.results.length ? <CalculationResults reply={calculationReply} regions={data?.regions ?? []} locked={locked} onSelect={selectResult} /> : null

  return <div className={`app app--${stage} app--${view}${briefingCards ? ' has-briefing' : ''}${briefingCards && phase === 'applying' ? ' briefing-presenting' : ''}${panel ? ' app--composer-open' : ''}${audio.active ? ' app--preview' : ''}`}>
    <div className="background-grid" aria-hidden="true" />
    <header className="interface-header">
      <div className="brand"><h1>NERVIS</h1><span>NEURAL DATA EXPLORER</span></div>
      <div className="header-center"><i />INTERACTIVE NEURAL INTERFACE<i /></div>
      <div className="header-actions">
      {ready && <div className="conversation-controls">
        <button disabled={locked || conversation.loading} onClick={() => { if (!historyOpen) void conversation.loadSessions(); setHistoryOpen(open => !open) }}>대화 기록{conversation.value ? ` · ${conversation.value.messages.length}` : ''}</button>
        <button disabled={locked || voiceActive || conversation.loading} onClick={() => { void newConversation() }}>새 대화</button>
        {conversation.error && <button disabled={locked || conversation.loading} onClick={() => { void conversation.reload() }}>기록 다시 불러오기</button>}
        {conversation.notice && <small role="status">{conversation.notice}</small>}
      </div>}
      <div className={`connection-chip state-${coreState}`} aria-live="polite"><span className="live-dot" />NERVIS / {stateLabels[coreState]}</div>
      </div>
    </header>

    {(stage === 'title' || stage === 'dock') && <div className="intro-caption"><span>AN INTERFACE TO EXPLORE</span><p>기록 속의 관계를 발견하다</p></div>}
    {!ready && <button className="skip-intro" onClick={() => setSkipped(true)}>인트로 건너뛰기 <span>↗</span></button>}

    <div className={`core-stage state-${coreState}`} aria-hidden="true">
      <div className="core-aura" />
      <div className="orbit-guide"><span className="orbit-notch n1" /><span className="orbit-notch n2" /><span className="orbit-notch n3" /></div>
      {(stage === 'core' || ready) && <CoreScene level={speech.active ? speech.level : audio.level} reduced={reduced} state={coreState} dense={view === 'home'} />}
      <div className="core-crosshair ch-left" /><div className="core-crosshair ch-right" />
    </div>

    <main className={`screen-content${ready ? ' is-ready' : ''}`} inert={!ready}>
      <section className="home-screen" hidden={view !== 'home'} aria-label="NERVIS 대화 홈">
        <div className={`core-caption state-${coreState}`}><span className="live-dot" />NERVIS / {stateLabels[coreState]}<small>PROCEDURAL CORE · LOCAL RENDER</small></div>
      </section>

      {explored && data && <div className="analysis-container" inert={audio.active || speech.active || pending(phase)} hidden={view !== 'analysis'}>
        <AnalysisView key={stageRequest?.id ?? 'preview'} request={stageRequest} onApplied={onApplied} onContext={onContext} regions={data.regions} version={data.summary.dataset_version} active={view === 'analysis'} blocked={audio.active || speech.active || phase === 'requesting'} reduced={reduced} onBusyChange={onStageBusy} response={resultPanel} calculations={calculations} tab={analysisTab} onTab={setAnalysisTab} />
      </div>}
    </main>

    <div className={`common-interface${ready ? ' is-ready' : ''}`} inert={!ready}>
      {ready && view === 'home' && <label className="briefing-preview-control"><input type="checkbox" aria-label="더미 브리핑 미리보기" checked={briefingPreview} disabled={locked} onChange={e => setBriefingPreview(e.target.checked)} />더미 미리보기</label>}
      {ready && view === 'home' && briefingCards && <BriefingCards key={briefingCards.id} value={briefingCards.value} reduced={reduced} onReady={onCardsReady} />}
      {view === 'home' && resultOpen && resultPanel}
      {view === 'home' && !resultOpen && resultPanel && <button className="result-reopen" onClick={() => setResultOpen(true)}>응답 다시 열기</button>}
      {ready && historyOpen && <ConversationHistory title={conversation.value?.title ?? '대화 기록'} messages={conversation.value?.messages ?? []}
        sessions={conversation.sessions} sessionId={conversation.value?.id} hasMore={conversation.hasMore} loading={conversation.listLoading}
        listError={conversation.listError} locked={locked || voiceActive || conversation.loading} onSelect={id => { void switchConversation(id) }}
        onMore={() => { void conversation.loadSessions(true) }} onRefresh={() => { void conversation.loadSessions() }} onClose={() => setHistoryOpen(false)} />}
      <Composer onVoiceActive={setVoiceActive} canSend={canSend} status={inputStatus} onSend={() => { void send() }} panel={panel} draft={draft} onDraft={setDraft} closable={view === 'analysis' || panel === 'voice'} locked={locked}
        onToggle={target => setPanel(current => toggleComposer(current, target, view))}
        onClose={() => setPanel(view === 'home' ? 'text' : null)} />
      <footer className="shell-footer">
        <div className="shell-actions"><span>INTERFACE / 02</span>
          <button className="local-view-button" disabled={locked || (view === 'home' && connection !== 'ready')} onClick={view === 'home' ? explore : home}>
            {view === 'home' ? '분석 화면 미리보기 ↗' : '대화 홈으로 ↖'}</button>
        </div>
        <div className="speech-actions" aria-label="로컬 응답 음성">
          {speech.active && <button onClick={speech.stop}>음성 중지</button>}
          <span role="status">{speech.phase === 'preparing' ? '로컬 음성 준비 중' : speech.phase === 'speaking' ? '응답 재생 중' : ''}</span>
        </div>
        <button className={`sound-preview${audio.active ? ' active' : ''}`} disabled={speech.active || voiceActive || pending(phase) || !ready || (view === 'analysis' && analysisBusy)} onClick={() => audio.active ? audio.stop() : void audio.play()}>
          <Icon name="sound" />{audio.active ? '미리보기 중지' : '코어 음량 반응 미리보기'}<small>로컬 합성음 · AI 음성 아님</small>
        </button>
        <button className="replay-button" onClick={restart} disabled={locked}>시작 연출 다시 보기 ↗</button>
      </footer>
      {!aiStatus && ready && <div className="ai-connection-error" role="status">AI 서버 연결을 확인하지 못했습니다. <button disabled={pending(phase)} onClick={() => { void refreshAI() }}>다시 확인</button></div>}
      {connection === 'error' && <div className="shell-error" role="alert"><p>{connectionError}</p><button onClick={() => setRetry(v => v + 1)}>서버 연결 다시 확인</button></div>}
    </div>
    {(speech.error || audio.error) && <p className="audio-error" role="alert">{speech.error || audio.error}</p>}
  </div>
}
