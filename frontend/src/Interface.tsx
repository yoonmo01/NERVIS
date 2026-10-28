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
    : voice.phase === 'listening' ? '듣는 중 · 확정 문장은 입력창에 추가됩니다.'
      : voice.phase === 'stopping' ? '마이크 꺼짐 · 마지막 문장 확정 대기 중'
        : '마이크 꺼짐 · 내용을 수정한 뒤 보내세요.')
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
    if (e.propertyName !== 'width' || (e.target !== e.currentTarget && (e.target as HTMLElement).id !== 'conversation-panel')) return
    const active = document.activeElement
    if (active && active !== document.body && !e.currentTarget.contains(active)) return
    if (panel) textInput.current?.focus()
  }} onKeyDown={e => {
    if (e.target === textInput.current && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && panel) { e.preventDefault(); if (sendReady && draft.trim()) onSend(); return }
    if (e.key === 'Escape' && !locked && closable && panel) { e.preventDefault(); onClose() }
  }}>
    <div className="composer-panel" id="conversation-panel" inert={!panel} aria-hidden={!panel}>
      {closable && <div className="composer-heading"><button className="composer-close" aria-label="입력창 닫기" disabled={locked} onClick={onClose}><Icon name="close" /></button></div>}
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
        <textarea ref={textInput} aria-label="NERVIS에게 보낼 내용" maxLength={600} rows={1} value={draft} disabled={locked} onChange={e => editDraft(e.target.value)} aria-describedby={statusMessage ? 'composer-status' : undefined} />
        <button className="send-button" disabled={!sendReady || !draft.trim()} title="명령 전송 · Enter" aria-label="명령 전송" onClick={onSend}><Icon name="send" /></button>
      </div>
      {statusMessage && <p id="composer-status" className="composer-status" role="status">{statusMessage}</p>}
    </div>
    <div className="composer-launchers">
      <button ref={textLauncher} aria-label="텍스트 입력창" aria-expanded={panel === 'text'} aria-controls="conversation-panel" disabled={locked || voice.active} onClick={() => onToggle('text')}>T</button>
      <button ref={voiceLauncher} aria-label={voice.active ? '마이크 끄기' : '마이크 켜기'} aria-pressed={voice.active} aria-expanded={panel === 'voice'} aria-controls="conversation-panel"
        className={voice.active ? 'selected' : ''} disabled={locked || voice.phase === 'stopping' || !!overflow} onClick={() => {
          if (voice.active) voice.stop()
          else { if (panel !== 'voice') onToggle('voice'); voice.start() }
        }}><Icon name="mic" /></button>
    </div>
  </section>
}
