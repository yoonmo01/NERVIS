import { ApiError } from './api.ts'
import type { AIReply, ViewContext } from './conversation.ts'

export interface RequestOwner { request_id: string; session_id: string }
export interface WorkEvent extends RequestOwner { type: string; tool?: string; index?: number }
interface ChatBody extends RequestOwner { command: string; context: ViewContext }

export async function streamChat(body: ChatBody, signal: AbortSignal, onEvent: (event: WorkEvent) => void): Promise<AIReply> {
  const response = await fetch('/api/ai/chat/stream', {
    method: 'POST', signal, cache: 'no-store',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify(body),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(response.status, typeof error.detail === 'string' ? error.detail : 'request_failed')
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) throw new Error('진행 이벤트 연결 형식을 확인하지 못했습니다.')
  const reader = response.body.getReader(), decoder = new TextDecoder()
  let buffer = ''
  const readEvent = (frame: string): AIReply | undefined => {
    const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n')
    if (!data) return
    const event = JSON.parse(data)
    if (!event || typeof event !== 'object' || event.request_id !== body.request_id || event.session_id !== body.session_id) throw new Error('다른 요청의 진행 응답이 도착했습니다.')
    if (event.type === 'error') throw new ApiError(Number.isInteger(event.status) ? event.status : 500, typeof event.code === 'string' ? event.code : 'request_failed')
    if (event.type === 'result') return event.reply as AIReply
    if (['request.started', 'model.started', 'explanation.started'].includes(event.type) ||
        (['tool.started', 'tool.completed'].includes(event.type) && typeof event.tool === 'string' && Number.isInteger(event.index) && event.index >= 0 && event.index < 6)) onEvent(event)
  }
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer = (buffer + decoder.decode(value, { stream: !done })).replace(/\r\n/g, '\n')
      if (buffer.length > 8_000_000) throw new Error('진행 응답의 허용 길이를 초과했습니다.')
      let boundary: number
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2)
        const reply = readEvent(frame)
        if (reply !== undefined) return reply
      }
      if (done) throw new Error('응답 완료 전에 연결이 끊겼습니다. 서버 처리가 계속될 수 있어 자동 재전송하지 않습니다.')
    }
  } finally {
    // A complete reply must not wait for transport cancellation to finish.
    void reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}

export function workMessage(event: WorkEvent): string {
  if (event.type === 'request.started') return '요청을 처리하고 있습니다.'
  if (event.type === 'model.started') return '요청에 필요한 작업을 확인하고 있습니다.'
  if (event.type === 'explanation.started') return '조회 결과를 바탕으로 설명을 준비하고 있습니다.'
  const name = event.tool === 'get_daily_briefing' ? '날씨·수업·할 일' : event.tool === 'get_weather' ? '날씨' : event.tool === 'list_tasks' ? '할 일' : event.tool === 'manage_tasks' ? '할 일 변경' : event.tool === 'register_courses' ? '수업 등록' : '분석'
  return event.type === 'tool.started' ? `${name} 처리 중입니다.` : `${name} 결과를 받았습니다. 응답을 정리하고 있습니다.`
}
