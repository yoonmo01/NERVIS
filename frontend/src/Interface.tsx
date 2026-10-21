import { useEffect, useRef, useState } from 'react'
import type { ComposerPanel } from './model.ts'

const paths = {
  mic: <><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 10v2a7 7 0 0 0 14 0v-2m-7 9v3m-4 0h8" /></>,
  send: <path d="m4 11 16-7-7 16-2-7-7-2Zm7 2 9-9" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  sound: <path d="M4 10v4m4-7v10m4-13v16m4-13v10m4-7v4" />,
}

export function Icon({ name }: { name: keyof typeof paths }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>
}

export function Composer({ panel, draft, onDraft, onToggle, onClose, locked, closable }: {
  panel: ComposerPanel; draft: string; onDraft: (value: string) => void;
  onToggle: (target: 'text' | 'voice') => void; onClose: () => void; locked: boolean; closable: boolean;
}) {
  const textInput = useRef<HTMLTextAreaElement>(null)
  const textLauncher = useRef<HTMLButtonElement>(null)
  const voiceLauncher = useRef<HTMLButtonElement>(null)
  const previousPanel = useRef(panel)
  const [lastPanel, setLastPanel] = useState(panel ?? 'text')
  const displayedPanel = panel ?? lastPanel
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
    if (e.key === 'Escape' && closable && panel) { e.preventDefault(); onClose() }
  }}>
    <div className="composer-panel" id="conversation-panel" inert={!panel} aria-hidden={!panel}>
      {closable && <div className="composer-heading"><button className="composer-close" aria-label="입력창 닫기" onClick={onClose}><Icon name="close" /></button></div>}
      <div className={`composer-field${displayedPanel === 'voice' ? ' is-voice' : ''}`}>
        {displayedPanel === 'voice' && <span className="voice-field-icon" aria-hidden="true"><Icon name="mic" /></span>}
        <textarea ref={textInput} aria-label="NERVIS에게 보낼 내용" maxLength={2000} rows={1} value={draft} disabled={locked} onChange={e => onDraft(e.target.value)} aria-describedby="composer-status" />
        <button className="field-mode-button" aria-label={displayedPanel === 'voice' ? '텍스트 입력 모드' : '음성 입력 모드'} aria-pressed={displayedPanel === 'voice'} disabled={locked} onClick={() => onToggle(displayedPanel === 'voice' ? 'text' : 'voice')}>{displayedPanel === 'voice' ? 'T' : <Icon name="mic" />}</button>
        <button className="send-button" disabled title="AI 연결 후 전송할 수 있습니다." aria-label="전송 · AI 미연결"><Icon name="send" /></button>
      </div>
      <p id="composer-status" className="composer-status">{locked ? '작업 진행 중 · 완료 후 입력할 수 있습니다.' : displayedPanel === 'text' ? 'AI 미연결 · 작성한 내용은 전송·저장되지 않습니다.' : '음성 모드 · STT 연결 전 · 마이크 꺼짐 · 텍스트 수정 가능'}</p>
    </div>
    {!panel && <div className="composer-launchers">
      <span className="composer-caption">대화 열기</span>
      <button ref={textLauncher} aria-label="텍스트 입력창" aria-expanded={false} aria-controls="conversation-panel" disabled={locked} onClick={() => onToggle('text')}>T</button>
      <button ref={voiceLauncher} aria-label="음성 입력 모드" aria-expanded={false} aria-controls="conversation-panel" disabled={locked} onClick={() => onToggle('voice')}><Icon name="mic" /></button>
    </div>}
  </section>
}
