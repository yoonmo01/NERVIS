import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../analysis/api.ts'

export interface ConversationMessage {
  id: number; role: 'user' | 'assistant'; content: string; status: 'running' | 'complete' | 'failed';
  created_at: string; usage: { input_tokens?: number; output_tokens?: number }[]; error?: string | null;
}
interface Conversation {
  id: string; title: string; state: { context?: { selected_region_ids: number[]; start: number; end: number } };
  messages: ConversationMessage[];
}
export interface ConversationListItem { id: string; title: string; updated_at: string; message_count: number }
const storageKey = 'nervis.conversation.v1'

export function useConversation() {
  const [value, setValue] = useState<Conversation | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [sessions, setSessions] = useState<ConversationListItem[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [listLoading, setListLoading] = useState(false)
  const [listError, setListError] = useState('')
  const listRef = useRef<ConversationListItem[]>([])
  const listController = useRef<AbortController | null>(null)
  const loadSessions = useCallback(async (more = false) => {
    listController.current?.abort()
    const controller = new AbortController()
    listController.current = controller
    setListLoading(true); setListError('')
    try {
      const offset = more ? listRef.current.length : 0
      const page = await api<{ sessions: ConversationListItem[]; has_more: boolean }>(`/api/conversations?limit=50&offset=${offset}`, controller.signal)
      if (!Array.isArray(page.sessions) || typeof page.has_more !== 'boolean') throw new Error('Invalid conversation list')
      if (alive.current && !controller.signal.aborted) {
        const combined = more ? [...listRef.current, ...page.sessions] : page.sessions
        listRef.current = combined.filter((item, index) => combined.findIndex(row => row.id === item.id) === index)
        setSessions(listRef.current); setHasMore(page.has_more)
        const title = listRef.current.find(item => item.id === current.current?.id)?.title
        if (title && current.current) {
          const id = current.current.id
          current.current = { ...current.current, title }
          setValue(previous => previous && previous.id === id ? { ...previous, title } : previous)
        }
      }
    } catch { if (alive.current && !controller.signal.aborted) setListError('대화 목록을 불러오지 못했습니다.') }
    finally { if (alive.current && !controller.signal.aborted) setListLoading(false) }
  }, [])
  const current = useRef<Conversation | null>(null)
  const restoringId = useRef<string | null>(null)
  const alive = useRef(true)
  const loadController = useRef<AbortController | null>(null)
  const accept = (next: Conversation) => {
    if (!next || typeof next.id !== 'string' || !Array.isArray(next.messages) || !next.state) throw new Error('대화 기록 형식을 확인해 주세요.')
    current.current = next
    restoringId.current = next.id
    if (alive.current) setValue(next)
    return next
  }
  const reload = useCallback(async (id?: string) => {
    const sid = id ?? current.current?.id ?? restoringId.current
    if (!sid) return
    restoringId.current = sid
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    setLoading(true); setError('')
    try {
      const next = accept(await api<Conversation>(`/api/conversations/${encodeURIComponent(sid)}`, controller.signal))
      try { localStorage.setItem(storageKey, next.id) }
      catch { setNotice('현재 대화는 서버에 저장되지만 브라우저에서 자동 복원할 수 없습니다.') }
      return next
    }
    catch {
      if (!controller.signal.aborted && alive.current) setError('대화 기록을 복원하지 못했습니다. DB·서버 연결을 확인하고 다시 불러오거나 새 대화를 시작해 주세요.')
    } finally { if (!controller.signal.aborted && alive.current) setLoading(false) }
  }, [])
  useEffect(() => {
    alive.current = true
    let sid: string | null = null
    try { sid = localStorage.getItem(storageKey) }
    catch { setNotice('브라우저 저장소를 사용할 수 없어 새로고침 후 대화가 자동 복원되지 않습니다.') }
    if (sid) { void reload(sid) } else setLoading(false)
    return () => { alive.current = false; loadController.current?.abort(); listController.current?.abort() }
  }, [reload])
  const create = async () => {
    setLoading(true); setError('')
    loadController.current?.abort()
    const controller = new AbortController()
    loadController.current = controller
    try {
      const next = accept(await api<Conversation>('/api/conversations', controller.signal, {}))
      try { localStorage.setItem(storageKey, next.id) }
      catch { setNotice('현재 대화는 서버에 저장되지만 브라우저에서 자동 복원할 수 없습니다.') }
      return next.id
    } catch (reason) {
      if (alive.current) setError('새 대화를 만들지 못했습니다. DB·서버 연결을 확인해 주세요.')
      throw reason
    } finally { if (alive.current) setLoading(false) }
  }
  const startNew = () => {
    loadController.current?.abort()
    current.current = null; restoringId.current = null
    setValue(null); setLoading(false); setError('')
    try { localStorage.removeItem(storageKey) }
    catch { setNotice('새 대화 선택을 브라우저에 저장하지 못했습니다. 새로고침하면 이전 세션이 복원될 수 있습니다.') }
  }
  return { value, loading, error, notice, reload, startNew, sessions, hasMore, listLoading, listError, loadSessions,
    ensure: async () => {
      if (error || loading) throw new Error('대화 복원이 끝난 뒤 다시 요청해 주세요.')
      return current.current?.id ?? create()
    } }
}
