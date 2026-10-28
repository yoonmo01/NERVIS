import { useEffect, useRef, useState } from 'react'
import type { ComposerPanel } from './model.ts'
import { appendTranscript } from './stt.ts'
import { useDictation } from './useDictation.ts'

const paths = {
  mic: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8" /></>,
  send: <path d="m4 11 16-7-7 16-2-7-7-2Zm7 2 9-9" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  sound: <path d="M4 10v4m4-7v10m4-13v16m4-13v10m4-7v4" />,
}

export function Icon({ name }: { name: keyof typeof paths }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

export function Composer({ panel, draft, onDraft, onToggle, onClose, locked, closable, canSend, status, onSend, onVoiceActive }: {
  panel: ComposerPanel; draft: string; onDraft: (value: string) => void;
  onToggle: (target: 'text' | 'voice') => void; onClose: () => void; locked: boolean; closable: boolean; canSend: boolean; status: string; onSend: () => void; onVoiceActive: (active: boolean) => void;
}) {
  const textInput = useRef<HTMLTextAreaElement>(null)
  const textLauncher = useRef<HTMLButtonElement>(null)
  const voiceLauncher = useRef<HTMLButtonElement>(null)
  const previousPanel = useRef(panel)
  const [lastPanel, setLastPanel] = useState(panel ?? 'text')
  const [overflow, setOverflow] = useState('')
  const overflowRef = useRef('')
  const draftRef = useRef(draft)
  draftRef.current = draft
  const editDraft = (value: string) => { draftRef.current = value; onDraft(value) }
  const editOverflow = (value: string) => { overflowRef.current = value; setOverflow(value) }
  const voice = useDictation(panel === 'voice' && !locked, text => {
    const next = overflowRef.current ? null : appendTranscript(draftRef.current, text)
    if (next === null) {
      editOverflow([overflowRef.current, text].filter(Boolean).join('\n'))
      voice.stop()
    } else editDraft(next)
  })
  useEffect(() => { onVoiceActive(voice.active || !!overflow); return () => onVoiceActive(false) }, [voice.active, overflow, onVoiceActive])
  const sendReady = canSend && !voice.active && !overflow
  const displayedPanel = panel ?? lastPanel
  const voiceStatus = voice.error || (voice.phase === 'starting' ? '마이크 권한 / 로컬 모델 준비 중 · 취소할 수 있습니다.'
    : voice.phase === 'listening' ? `마이크 켜짐 · Turbo / 한국어 고정 / ${voice.device} · 최대 2분 · 확정 문장을 초안 뒤에 추가합니다.`
      : voice.phase === 'stopping' ? '마이크 꺼짐 · 마지막 문장 확정 대기 중'
        : '마이크 꺼짐 · 로컬 Turbo / 한국어 고정 · 확정 문장을 수정한 뒤 보내기를 누르세요.')
  const statusMessage = locked ? '작업 진행 중 · 완료 후 입력할 수 있습니다.' : displayedPanel === 'text' ? status : voiceStatus
  useEffect(() => {
    const previous = previousPanel.current
    previousPanel.current = panel
    if (panel) setLastPanel(panel)
    if (previous === panel) return
    if (panel) textInput.current?.focus()
    else (previous === 'voice' ? voiceLauncher : textLauncher).current?.focus()
  }, [panel])
  return <section className={`composer${panel ? ' composer--open' : ''}`} aria-label="NERVIS 대화 입력" onTransitionEnd={e => {
    // The closed drawer is invisible, so restore focus after its opening transition.
    if (e.target !== e.currentTarget || e.propertyName !== 'width') return
    const active = document.activeElement
    if (active && active !== document.body && !e.currentTarget.contains(active)) return
    if (panel) textInput.current?.focus()
  }} onKeyDown={e => {
    if (e.target === textInput.current && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && panel) { e.preventDefault(); if (sendReady && draft.trim()) onSend(); return }
    if (e.key === 'Escape' && !locked && closable && panel) { e.preventDefault(); onClose() }
  }}>
    <div className="composer-panel" id="conversation-panel" inert={!panel} aria-hidden={!panel}>
      {closable && <div className="composer-heading"><button className="composer-close" aria-label="입력창 닫기" disabled={locked} onClick={onClose}><Icon name="close" /></button></div>}
      {displayedPanel === 'voice' && <div className="dictation-controls">
        <button className={`dictation-toggle${voice.phase === 'listening' ? ' is-recording' : ''}`} disabled={locked || voice.phase === 'stopping' || (!voice.active && !!overflow)}
          aria-pressed={voice.active} onClick={voice.active ? voice.stop : voice.start}><Icon name="mic" />{voice.phase === 'starting' ? '마이크 시작 취소' : voice.phase === 'listening' ? '마이크 끄기' : voice.phase === 'stopping' ? '확정 대기 중' : '마이크 켜기'}</button>
        <span>이 컴퓨터에서 한국어 인식 · 자동 전송 없음</span>
      </div>}
      {voice.partial && <p className="dictation-partial" role="status"><strong>인식 중 · 미확정</strong> {voice.partial}</p>}
      {overflow && <div className="dictation-overflow">
        <label htmlFor="dictation-overflow">600자 한도 초과 · 추가하지 못한 확정 문장 (수정·복사 가능)</label>
        <textarea id="dictation-overflow" value={overflow} onChange={e => editOverflow(e.target.value)} />
        <button disabled={locked || voice.active || appendTranscript(draft, overflow) === null} onClick={() => {
          const next = appendTranscript(draftRef.current, overflow)
          if (next !== null) { editDraft(next); editOverflow('') }
        }}>초안 뒤에 추가</button>
      </div>}
      <div className={`composer-field${displayedPanel === 'voice' ? ' is-voice' : ''}`}>
        {displayedPanel === 'voice' && <span className="voice-field-icon" aria-hidden="true"><Icon name="mic" /></span>}
        <textarea ref={textInput} aria-label="NERVIS에게 보낼 내용" maxLength={600} rows={1} value={draft} disabled={locked} onChange={e => editDraft(e.target.value)} aria-describedby={statusMessage ? 'composer-status' : undefined} />
        <button className="field-mode-button" aria-label={displayedPanel === 'voice' ? '텍스트 입력 모드' : '음성 입력 모드'} aria-pressed={displayedPanel === 'voice'} disabled={locked} onClick={() => onToggle(displayedPanel === 'voice' ? 'text' : 'voice')}>{displayedPanel === 'voice' ? 'T' : <Icon name="mic" />}</button>
        <button className="send-button" disabled={!sendReady || !draft.trim()} title="명령 전송 · Enter" aria-label="명령 전송" onClick={onSend}><Icon name="send" /></button>
      </div>
      {statusMessage && <p id="composer-status" className="composer-status" role="status">{statusMessage}</p>}
    </div>
    {!panel && <div className="composer-launchers">
      <button ref={textLauncher} aria-label="텍스트 입력창" aria-expanded={false} aria-controls="conversation-panel" disabled={locked} onClick={() => onToggle('text')}>T</button>
      <button ref={voiceLauncher} aria-label="음성 입력 모드" aria-expanded={false} aria-controls="conversation-panel" disabled={locked} onClick={() => onToggle('voice')}><Icon name="mic" /></button>
    </div>}
  </section>
}
