import { useCallback, useEffect, useRef, useState } from 'react'
import CoreScene from './components/CoreScene.tsx'
import ConversationHistory from './features/conversation/ConversationHistory.tsx'
import { useConversation } from './features/conversation/useConversation.ts'
import { isTaskTool } from './features/briefing/tasks.ts'
import AnalysisView from './features/analysis/AnalysisView.tsx'
import BriefingCards from './features/briefing/BriefingCards.tsx'
import { briefingFromResults } from './features/briefing/briefing.ts'
import type { Briefing } from './features/briefing/briefing.ts'
import { api, ApiError } from './features/analysis/api.ts'
import type { Region, Summary } from './features/analysis/api.ts'
import { INTRO, introStage, toggleComposer } from './components/model.ts'
import type { ComposerPanel, IntroStage } from './components/model.ts'
import { useSpeech } from './features/speech/useSpeech.ts'
import { Composer } from './features/conversation/Interface.tsx'
import ConversationPanel, { CalculationResults } from './features/conversation/ConversationPanel.tsx'
import { checkedReply, viewSelection, pending, aiErrorMessage, interfaceState } from './features/conversation/conversation.ts'
import type { AIStatus, AIReply, CommandPhase, ViewContext, ViewRequest } from './features/conversation/conversation.ts'
import type { StageSelection } from './features/analysis/stageData.ts'
import { streamChat, workMessage } from './features/conversation/chatStream.ts'
import type { RequestOwner } from './features/conversation/chatStream.ts'
import { useActivation } from './features/activation/useActivation.ts'

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
  const [pageVisible, setPageVisible] = useState(() => !document.hidden)
  const conversation = useConversation()
  const speech = useSpeech()
  const ownerRef = useRef<RequestOwner | null>(null)
  const [owner, setOwner] = useState<RequestOwner | null>(null)
  const [workStatus, setWorkStatus] = useState('')
  const stageOwner = useRef<RequestOwner | null>(null)
  const stagingId = useRef<number | null>(null)
  const [preparedAnalysis, setPreparedAnalysis] = useState<{ request: ViewRequest; ready: boolean } | null>(null)
  const [awaitingPlayback, setAwaitingPlayback] = useState<{ owner: RequestOwner; view: 'home' | 'analysis' | null; shown: boolean; started?: boolean } | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [stage, setStage] = useState<IntroStage>(() => introStage(0, reduced))
  const [view, setView] = useState<'home' | 'analysis'>('home')
  const [explored, setExplored] = useState(false)
  const [panel, setPanel] = useState<ComposerPanel>(null)
  const [draft, setDraft] = useState('')
  const [voiceActive, setVoiceActive] = useState(false)
  const [introStarted, setIntroStarted] = useState(false)
  const [voiceTrigger, setVoiceTrigger] = useState(0)
  const [briefingCards, setBriefingCards] = useState<{ id: number; value: Briefing; owner: RequestOwner } | null>(null)
  const cardsFlight = useRef(false)
  const onCardsReady = useCallback((requestId: string) => {
    if (!cardsFlight.current || ownerRef.current?.request_id !== requestId) return
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
    const leave = () => {
      if (controller.current) {
        controller.current.abort()
        setRequestError('화면을 벗어나 응답 연결을 중지했습니다. 서버 처리는 계속될 수 있으니 대화 기록을 확인해 주세요.')
        setPhase('error')
      } else setPhase(previous => previous === 'applying' ? 'complete' : previous)
      ownerRef.current = null; setOwner(null); speech.claim(null); setWorkStatus('')
      expectedStage.current = null; cardsFlight.current = false; flight.current = false
      stagingId.current = null; setPreparedAnalysis(null); setAwaitingPlayback(null)
    }
    const visibility = () => setPageVisible(!document.hidden)
    window.addEventListener('focus', focus)
    window.addEventListener('pagehide', leave); document.addEventListener('visibilitychange', visibility)
    return () => {
      mounted.current = false; ownerRef.current = null; controller.current?.abort()
      window.removeEventListener('focus', focus); window.removeEventListener('pagehide', leave); document.removeEventListener('visibilitychange', visibility)
    }
  }, [refreshAI])
  useEffect(() => {
    if (!aiStatus?.busy) return
    const timer = setInterval(() => { void refreshAI() }, 1500)
    return () => clearInterval(timer)
  }, [aiStatus?.busy, refreshAI])
  const onContext = useCallback((value: ViewContext) => { context.current = value }, [])
  const onApplied = useCallback((id: number, error?: string) => {
    if (expectedStage.current !== id || (stageOwner.current && stageOwner.current.request_id !== ownerRef.current?.request_id)) return
    if (!error && stagingId.current === id) {
      setPreparedAnalysis(previous => previous?.request.id === id ? { ...previous, ready: true } : previous)
      return
    }
    if (error) { stagingId.current = null; setPreparedAnalysis(null); setAwaitingPlayback(null) }
    expectedStage.current = null; flight.current = false
    setRequestError(error ? `계산 결과는 받았지만 화면 적용에 실패했습니다: ${error}` : '')
    if (error) {
      speech.stop()
      if (ownerRef.current) void speech.play(`계산 결과는 받았지만 화면 적용에 실패했습니다: ${error}`, [], ownerRef.current)
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
    stageOwner.current = ownerRef.current
    setStageRequest({ id, selection }); setExplored(true); setView('analysis'); setPanel(null); setPhase('applying')
  }
  const send = async () => {
    if (flight.current || locked || voiceActive || !aiStatus?.enabled || aiStatus.busy || !draft.trim() || !data) return
    flight.current = true; expectedStage.current = null
    let requestOwner: RequestOwner = { request_id: crypto.randomUUID(), session_id: conversation.value?.id ?? crypto.randomUUID() }
    ownerRef.current = requestOwner; setOwner(requestOwner); speech.claim(requestOwner)
    speech.prepare()
    const submitted = draft.trim(), current = new AbortController()
    controller.current = current
    const ownsRequest = () => mounted.current && ownerRef.current?.request_id === requestOwner.request_id
    let receipt = Promise.resolve(), acknowledged = false
    const acknowledge = () => {
      if (acknowledged || !ownsRequest() || current.signal.aborted) return
      acknowledged = true; receipt = activation.acknowledge()
    }
    setWorkStatus('요청을 연결하고 있습니다.')
    setCommand(submitted); setReply(null); setRequestError(''); setPhase('requesting'); setResultOpen(true); setAnalysisTab('response')
    setBriefingCards(null); cardsFlight.current = false
    const timeout = setTimeout(() => current.abort(), 180000)
    try {
      const sessionId = await conversation.ensure()
      if (!ownsRequest() || current.signal.aborted) return
      requestOwner = { ...requestOwner, session_id: sessionId }
      ownerRef.current = requestOwner; setOwner(requestOwner); speech.claim(requestOwner)
      const packet = await streamChat({ command: submitted, context: context.current, ...requestOwner }, current.signal, event => {
        if (ownsRequest() && !current.signal.aborted && event.session_id === requestOwner.session_id) {
          if (event.type === 'request.started') acknowledge()
          setWorkStatus(workMessage(event))
        }
      })
      await receipt
      const response = checkedReply(packet, data.summary.dataset_version)
      if (!ownsRequest() || current.signal.aborted) return
      const selection = viewSelection(response)
      const briefing = briefingFromResults(response.results)
      setReply(response); setDraft('')
      setWorkStatus('결과를 받았습니다. 화면과 음성을 준비하고 있습니다.')
      setPanel(null); setPhase('applying')
      setAwaitingPlayback({ owner: requestOwner, view: selection ? 'analysis' : briefing || response.results.some(result => isTaskTool(result.tool)) ? 'home' : null, shown: false })
      void speech.play(response.model_acknowledgement?.trim() || '요청 결과를 화면에서 확인해 주세요.', [], requestOwner, true)
      if (selection) {
        const request = { id: ++sequence.current, selection }
        expectedStage.current = request.id; stagingId.current = request.id; stageOwner.current = requestOwner
        setPreparedAnalysis({ request, ready: false })
      }
      else if (briefing) {
        setBriefingCards({ id: ++sequence.current, value: briefing, owner: requestOwner }); cardsFlight.current = true
      }
    } catch (error) {
      await receipt
      if (!ownsRequest()) return
      const message = error instanceof ApiError ? aiErrorMessage(error.code) : error instanceof DOMException && error.name === 'AbortError'
        ? '응답을 3분 안에 받지 못했습니다. 서버 처리가 계속될 수 있어 자동 재전송하지 않습니다.'
        : error instanceof Error ? error.message : '요청을 완료하지 못했습니다.'
      setRequestError(message); setWorkStatus(''); void speech.play(message, [], requestOwner)
      setPhase('error'); flight.current = false
    } finally {
      clearTimeout(timeout)
      if (controller.current === current) controller.current = null
      if (ownsRequest()) { void refreshAI(); void conversation.reload(); if (historyOpen) void conversation.loadSessions() }
    }
  }
  const resetConversationView = () => {
    stagingId.current = null; setPreparedAnalysis(null); setAwaitingPlayback(null)
    ownerRef.current = null; setOwner(null); speech.claim(null); setWorkStatus(''); expectedStage.current = null; cardsFlight.current = false
    setReply(null); setCommand(''); setDraft(''); setPhase('idle'); setRequestError('')
    setBriefingCards(null); setStageRequest(null); setExplored(false); setView('home'); setPanel(null)
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
  const stopResponse = () => {
    stagingId.current = null; setPreparedAnalysis(null); setAwaitingPlayback(null)
    speech.claim(null); ownerRef.current = null; setOwner(null); setWorkStatus('')
    expectedStage.current = null; cardsFlight.current = false; flight.current = false
    setPhase(previous => previous === 'applying' ? 'complete' : previous)
  }
  const speechOwned = !!owner && speech.owner?.request_id === owner.request_id && speech.owner?.session_id === owner.session_id
  const speechTarget = speechOwned ? speech.target : null

  useEffect(() => {
    if (!awaitingPlayback || ownerRef.current?.request_id !== awaitingPlayback.owner.request_id || !speechOwned) return
    if (speech.phase !== 'ready' && speech.phase !== 'error' && !awaitingPlayback.started) return
    if (awaitingPlayback.view === 'analysis' && !awaitingPlayback.shown && !preparedAnalysis?.ready) {
      // A hidden tab may suspend WebGL frames. Audio must not wait for those frames.
      if (!pageVisible && speech.phase === 'ready' && !awaitingPlayback.started) {
        void speech.start(awaitingPlayback.owner)
        setAwaitingPlayback({ ...awaitingPlayback, started: true })
      }
      return
    }
    if (!awaitingPlayback.shown) {
      if (awaitingPlayback.view === 'analysis' && preparedAnalysis) {
        setStageRequest(preparedAnalysis.request); setExplored(true); setPreparedAnalysis(null); stagingId.current = null
      }
      if (awaitingPlayback.view) setView(awaitingPlayback.view)
      setAwaitingPlayback({ ...awaitingPlayback, shown: true })
      return
    }
    // Start only after the prepared screen has been committed to the DOM.
    if (speech.phase === 'ready' && !awaitingPlayback.started) void speech.start(awaitingPlayback.owner)
    setAwaitingPlayback(null); expectedStage.current = null; flight.current = false
    cardsFlight.current = false; setWorkStatus(''); setPhase('complete')
  }, [awaitingPlayback, preparedAnalysis, speechOwned, speech.phase, speech.start, pageVisible])

  useEffect(() => {
    if (!introStarted) { setStage('title'); return }
    setStage(introStage(0, reduced))
    if (reduced) return
    const timers = Object.values(INTRO).map(time => setTimeout(() => setStage(introStage(time)), time))
    return () => timers.forEach(clearTimeout)
  }, [reduced, introStarted])

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

  const ready = introStarted && stage === 'ready'
  const baseLocked = !ready || speech.active || pending(phase) || (view === 'analysis' && analysisBusy)
  const activation = useActivation(introStarted, !baseLocked && !voiceActive && panel === null && !historyOpen,
    () => { setIntroStarted(true) },
    () => { setPanel('voice'); setVoiceTrigger(value => value + 1) })
  const locked = baseLocked || activation.greeting
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if (event.code !== 'Space' || !event.ctrlKey || !event.shiftKey || event.repeat) return
      event.preventDefault()
      if (!introStarted) { activation.stop(); activation.begin(); return }
      if (!locked) { activation.stop(); setPanel('voice'); setVoiceTrigger(value => value + 1) }
    }
    window.addEventListener('keydown', shortcut)
    return () => window.removeEventListener('keydown', shortcut)
  }, [introStarted, locked, activation.stop])
  const canSend = !locked && (!conversation.loading && !conversation.error) && connection === 'ready' && (!!aiStatus?.enabled && !aiStatus.busy)
  const inputStatus = conversation.loading ? '대화 기록을 불러오는 중입니다.' : conversation.error ? conversation.error : !aiStatus ? 'AI 서버 연결을 확인해 주세요.' : aiStatus.busy ? '이전 요청을 처리 중입니다.' : !aiStatus.enabled ? 'AI가 비활성 상태입니다. 서버 설정을 확인해 주세요.' : ''
  const corePhase = phase === 'complete' && reply?.status === 'partial' && reply.explanation_source !== 'local_results' ? 'error' : phase
  const coreState = speech.active ? speech.phase === 'speaking' ? 'speaking' : 'processing'
    : interfaceState(corePhase !== 'error' && corePhase !== 'requesting' && view === 'analysis' && analysisBusy ? 'applying' : corePhase, connection !== 'error', !!aiStatus?.enabled, !!aiStatus?.busy, false)
  const stateLabels = { standby: 'STANDBY', processing: 'PROCESSING', analyzing: 'ANALYZING', error: 'ERROR', paused: 'PAUSED', preview: 'AUDIO PREVIEW', speaking: 'SPEAKING' }
  const selectResult = (selection: StageSelection) => { if (!flight.current && !locked) { setRequestError(''); applySelection(selection) } }
  const briefingIndex = reply?.results.findIndex(r => r.tool === 'get_daily_briefing') ?? -1
  const briefingPrefix = `r${briefingIndex >= 0 ? briefingIndex : reply?.results.findIndex(r => r.tool === 'get_weather') ?? 0}`
  const resultPanel = phase === 'idle' ? null : <ConversationPanel phase={phase} command={command} reply={reply} error={requestError} regions={data?.regions ?? []} locked={locked} docked={view === 'analysis'} activeTarget={speechTarget} progress={workStatus}
    onSelect={selectResult}
    onClose={() => { if (!flight.current) setResultOpen(false) }} />
  const calculationReply = reply ? { ...reply, results: reply.results.filter(r => r.tool !== 'get_daily_briefing' && r.tool !== 'get_weather' && !isTaskTool(r.tool)) } : null
  const calculations = calculationReply?.results.length ? <CalculationResults reply={calculationReply} regions={data?.regions ?? []} locked={locked} onSelect={selectResult} /> : null

  return <div className={`app app--${stage} app--${view}${briefingCards ? ' has-briefing' : ''}${briefingCards && phase === 'applying' ? ' briefing-presenting' : ''}${panel ? ' app--composer-open' : ''}`}>
    <div className="background-grid" aria-hidden="true" />
    <header className="interface-header">
      <div className="brand"><h1>NERVIS</h1><span>NEURAL DATA EXPLORER</span></div>
      <div className="header-center"><i />INTERACTIVE NEURAL INTERFACE<i /></div>
      <div className="header-actions">
      {ready && <div className="activation-controls">
        {activation.greeting && <button onClick={() => activation.stop()}>안내음 중지</button>}
        <button aria-pressed={activation.armed} disabled={baseLocked || voiceActive || activation.greeting} onClick={() => activation.armed ? activation.stop() : void activation.arm()}>{activation.armed ? '음성 호출 끄기' : '음성 호출 켜기'}</button>
      </div>}
      {speech.active && <button className={`speech-stop state-${coreState}`} onClick={stopResponse} aria-label="응답 음성 중지" title="응답 음성 중지">■</button>}
      {ready && view === 'analysis' && <button disabled={locked || voiceActive} onClick={() => { setPanel(null); setView('home') }}>대화 홈</button>}
      {ready && <div className="conversation-controls">
        <button disabled={locked || conversation.loading} onClick={() => { if (!historyOpen) void conversation.loadSessions(); setHistoryOpen(open => !open) }}>대화 기록{conversation.value ? ` · ${conversation.value.messages.length}` : ''}</button>
        <button disabled={locked || voiceActive || conversation.loading} onClick={() => { void newConversation() }}>새 대화</button>
        {conversation.error && <button disabled={locked || conversation.loading} onClick={() => { void conversation.reload() }}>기록 다시 불러오기</button>}
        {conversation.notice && <small role="status">{conversation.notice}</small>}
      </div>}
      <div className={`connection-chip state-${coreState}`} aria-live="polite"><span className="live-dot" />NERVIS / {stateLabels[coreState]}</div>
      </div>
    </header>

    {(stage === 'title' || stage === 'dock') && <div className="intro-caption"><span>AN INTERFACE TO EXPLORE</span><p></p></div>}
    {!introStarted && <div className="activation-wait" role="region" aria-label="NERVIS 시작 대기">
      <p>{activation.armed ? '박수 두 번으로 시작하세요' : ''}</p>
      <small>{activation.armed ? '짝, 짝 · 박수 두 번을 기다리고 있습니다.' : '마이크 연결 후 박수 두 번으로 시작합니다.'}</small>
      <button onClick={() => activation.armed ? activation.stop() : void activation.arm()}>{activation.armed ? '연결 해제' : 'NERVIS 깨우기'}</button>
    </div>}

    <div className={`core-stage state-${coreState}`} aria-hidden="true">
      <div className="core-aura" />
      <div className="orbit-guide"><span className="orbit-notch n1" /><span className="orbit-notch n2" /><span className="orbit-notch n3" /></div>
      {(stage === 'core' || ready) && <CoreScene level={speech.level} reduced={reduced} state={coreState} dense={view === 'home'} />}
      <div className="core-crosshair ch-left" /><div className="core-crosshair ch-right" />
    </div>

    <main className={`screen-content${ready ? ' is-ready' : ''}`} inert={!ready}>
      <section className="home-screen" hidden={view !== 'home'} aria-label="NERVIS 대화 홈">
        <div className={`core-caption state-${coreState}`}><span className="live-dot" />NERVIS / {stateLabels[coreState]}<small>PROCEDURAL CORE · LOCAL RENDER</small></div>
      </section>

      {data && [...(explored ? [{ request: stageRequest, preparing: false }] : []), ...(preparedAnalysis ? [{ request: preparedAnalysis.request, preparing: true }] : [])].map(entry =>
        <div key={entry.request?.id ?? 'preview'} className="analysis-container" style={entry.preparing ? { visibility: 'hidden', pointerEvents: 'none' } : undefined}
          aria-hidden={entry.preparing || view !== 'analysis'} inert={entry.preparing || phase === 'requesting'} hidden={!entry.preparing && view !== 'analysis'}>
          <AnalysisView request={entry.request} onApplied={onApplied} onContext={onContext} regions={data.regions} version={data.summary.dataset_version}
            active={entry.preparing || view === 'analysis'} presenting={!entry.preparing && view === 'analysis'} blocked={phase === 'requesting'} reduced={reduced}
            onBusyChange={onStageBusy} response={resultPanel} calculations={calculations} tab={analysisTab} onTab={setAnalysisTab} />
        </div>)}
    </main>

    <div className={`common-interface${ready ? ' is-ready' : ''}`} inert={!ready}>
      {ready && view === 'home' && briefingCards && !awaitingPlayback && <BriefingCards key={briefingCards.id} value={briefingCards.value} reduced={reduced} onReady={() => onCardsReady(briefingCards.owner.request_id)}
        prefix={briefingPrefix}
        playback={{ active: speechOwned && briefingCards.owner.request_id === owner?.request_id && speech.active && speech.synchronized === true, target: speechTarget }} />}
      {view === 'home' && resultOpen && resultPanel}
      {view === 'home' && !resultOpen && resultPanel && <button className="result-reopen" onClick={() => setResultOpen(true)}>응답 다시 열기</button>}
      {ready && historyOpen && <ConversationHistory title={conversation.value?.title ?? '대화 기록'} messages={conversation.value?.messages ?? []}
        sessions={conversation.sessions} sessionId={conversation.value?.id} hasMore={conversation.hasMore} loading={conversation.listLoading}
        listError={conversation.listError} locked={locked || voiceActive || conversation.loading} onSelect={id => { void switchConversation(id) }}
        onMore={() => { void conversation.loadSessions(true) }} onRefresh={() => { void conversation.loadSessions() }} onClose={() => setHistoryOpen(false)} />}
      <Composer voiceTrigger={voiceTrigger} beforeVoice={() => activation.stop()} onVoiceActive={setVoiceActive} canSend={canSend} status={inputStatus} onSend={() => { void send() }} panel={panel} draft={draft} onDraft={setDraft} closable={true} locked={locked}
        onToggle={target => { activation.stop(); setPanel(current => toggleComposer(current, target, view)) }}
        onClose={() => setPanel(null)} />

      {!aiStatus && ready && <div className="ai-connection-error" role="status">AI 서버 연결을 확인하지 못했습니다. <button disabled={pending(phase)} onClick={() => { void refreshAI() }}>다시 확인</button></div>}
      {connection === 'error' && <div className="shell-error" role="alert"><p>{connectionError}</p><button onClick={() => setRetry(v => v + 1)}>서버 연결 다시 확인</button></div>}
    </div>
    {activation.notice && <p className="activation-notice" role="status">{activation.notice}</p>}
    {speech.error && <p className="audio-error" role="alert">{speech.error}</p>}
  </div>
}
