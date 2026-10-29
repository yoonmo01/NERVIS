import type { AIReply, LocalResult } from './conversation.ts'
import type { Briefing, BriefingStage } from './briefing.ts'

export interface SpeechSegment { text: string; target: string }

export function presentationTargets(results: LocalResult[]): Set<string> {
  const targets = new Set(['response'])
  const daily = results.findIndex(r => r.tool === 'get_daily_briefing')
  const briefing = daily >= 0 ? daily : results.findIndex(r => r.tool === 'get_weather')
  const task = results.findIndex(r => ['list_tasks', 'manage_tasks', 'register_courses'].includes(r.tool))
  const analysis = results.some(r => !['get_daily_briefing', 'get_weather', 'list_tasks', 'manage_tasks', 'register_courses'].includes(r.tool))
  results.forEach((result, index) => {
    const prefix = `r${index}`, data = result.data
    const add = (kind: string, rows: unknown, limit = 20, hideDone = false) => {
      targets.add(`${prefix}.${kind}`)
      if (Array.isArray(rows)) rows.slice(0, limit).forEach((row, i) => { if (!hideDone || row.status !== 'done') targets.add(`${prefix}.${kind}.${i}`) })
    }
    if (index === briefing && !analysis) {
      targets.add(`${prefix}.weather`)
      if (result.tool === 'get_daily_briefing') { add('classes', data.classes, 12); add('tasks', data.tasks, 20, true) }
    } else if (index === task && (briefing < 0 || analysis) && (result.tool === 'list_tasks' || result.tool === 'manage_tasks')) add('tasks', data.items)
  })
  return targets
}

export function presentationSegments(reply: AIReply): SpeechSegment[] {
  const value = reply.segments, answer = reply.model_acknowledgement
  if (!Array.isArray(value) || !value.length || value.length > 12 || !answer || answer.length > 2000) return []
  const allowed = presentationTargets(reply.results)
  if (!value.every(s => s && typeof s.text === 'string' && s.text.trim() && typeof s.target === 'string' && allowed.has(s.target))) return []
  const normalize = (text: string) => text.replace(/\s+/g, ' ').trim()
  return normalize(value.map(s => s.text).join(' ')) === normalize(answer) ? value : []
}

export function briefingCue(target: string | null | undefined): BriefingStage {
  const kind = target?.split('.')[1]
  return kind === 'weather' || kind === 'classes' || kind === 'tasks' ? kind : 'overview'
}

export function briefingPlaybackStage(playback: { active: boolean; target?: string | null }, prefix: string, reduced: boolean, skipped: boolean): BriefingStage {
  if (reduced || skipped || !playback.active) return 'docked'
  if (!playback.target) return 'waiting'
  return briefingCue(playback.target.startsWith(prefix + '.') ? playback.target : 'response')
}

export function previewSegments(value: Briefing, weatherOnly: boolean): SpeechSegment[] {
  const parts = [{ text: '더미 데이터로 음성과 화면 연결을 미리 보여드립니다.', target: 'response' },
    { text: `${value.weather.location} 날씨는 ${value.weather.current?.temperature_c ?? '정보 없음'}도입니다.`, target: 'r0.weather' }]
  if (!weatherOnly) {
    parts.push({ text: `등록된 수업은 ${value.classes.length}개입니다.`, target: 'r0.classes' })
    value.classes.slice(0, 3).forEach((row, i) => parts.push({ text: `${row.starts_at.slice(0, 5)}에 ${row.course_name} 수업이 있습니다.`, target: `r0.classes.${i}` }))
    parts.push({ text: `해야 할 일은 ${value.tasks.length}개입니다.`, target: 'r0.tasks' })
    value.tasks.slice(0, 5).forEach((row, i) => parts.push({ text: `${row.title}.`, target: `r0.tasks.${i}` }))
  }
  return parts
}
