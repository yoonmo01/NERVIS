import ReactMarkdown from 'react-markdown'
import type { ConversationListItem, ConversationMessage } from './useConversation.ts'

export default function ConversationHistory({ title, messages, sessions, sessionId, hasMore, loading, listError, locked, onSelect, onMore, onRefresh, onClose }: {
  title: string; messages: ConversationMessage[]; sessions: ConversationListItem[]; sessionId?: string;
  hasMore: boolean; loading: boolean; listError: string; locked: boolean;
  onSelect: (id: string) => void; onMore: () => void; onRefresh: () => void; onClose: () => void;
}) {
  return <aside className="conversation-history framed" aria-label="세션별 대화 기록">
    <header><h2>{title}</h2><button onClick={onClose} aria-label="대화 기록 닫기">×</button></header>
    <div className="conversation-history-body">
      <nav className="conversation-session-list" aria-label="대화 세션 목록">
        {sessions.map(session => <button key={session.id} className={session.id === sessionId ? 'is-current' : ''}
          aria-current={session.id === sessionId ? 'true' : undefined} disabled={locked}
          onClick={() => onSelect(session.id)}>
          <strong>{session.title}</strong><small>{new Date(session.updated_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })} · {session.message_count}개 메시지</small>
        </button>)}
        {!sessions.length && !loading && !listError && <p>저장된 대화가 없습니다.</p>}
        {loading && <p role="status">목록 불러오는 중…</p>}
        {listError && <p role="alert">{listError}<button disabled={loading} onClick={onRefresh}>다시 불러오기</button></p>}
        {hasMore && <button disabled={loading} onClick={onMore}>이전 대화 더 보기</button>}
      </nav>
      <div className="conversation-history-messages">
      {!messages.length && <p>아직 저장된 대화가 없습니다.</p>}
      {messages.map(message => <article key={message.id} className={`history-message role-${message.role}`}>
        <span>{message.role === 'user' ? 'YOU' : 'NERVIS'} · {new Date(message.created_at).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}</span>
        <ReactMarkdown>{message.content}</ReactMarkdown>
        {message.status !== 'complete' && <small>{message.status === 'running' ? '응답 확인 전 · 자동 재전송하지 않습니다.' : '처리 실패 · 자동 재전송하지 않습니다.'}</small>}
      </article>)}
      </div>
    </div>
  </aside>
}
