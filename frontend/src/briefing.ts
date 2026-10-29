import type { Weather } from './weather.ts'

export interface Briefing {
  date: string; preview: boolean; weatherOnly?: boolean; calendar_status?: string;
  classes: { course_name: string; starts_at: string; ends_at: string; location?: string | null }[];
  tasks: { title: string; status: string; task_group?: 'overdue' | 'today' | 'remaining'; planned_on?: string | null; due_on?: string | null; due_time?: string | null }[];
  weather: Weather;
  has_more_classes?: boolean; has_more_tasks?: boolean;
}

export type BriefingStage = 'waiting' | 'weather' | 'classes' | 'tasks' | 'overview' | 'docking' | 'docked'

export function checkBriefing(data: Record<string, unknown>, tool: string) {
  const weather = (tool === 'get_weather' ? data : data.weather) as Weather
  if (!weather || typeof weather.location !== 'string' || typeof weather.status !== 'string' || !Array.isArray(weather.hourly) ||
      (weather.current !== null && (!weather.current || !Number.isFinite(weather.current.temperature_c)))) throw new Error('날씨 응답 형식을 확인해 주세요.')
  if (tool === 'get_weather') {
    if (data.kind !== 'weather') throw new Error('날씨 응답 종류가 올바르지 않습니다.')
    return
  }
  if (data.kind !== 'briefing' || typeof data.date !== 'string' || !Array.isArray(data.classes) || data.classes.length > 200 ||
      !Array.isArray(data.tasks) || data.tasks.length > 200 ||
      data.classes.some(row => !row || typeof row.course_name !== 'string' || typeof row.starts_at !== 'string' || typeof row.ends_at !== 'string') ||
      data.tasks.some(row => !row || typeof row.title !== 'string' || typeof row.status !== 'string' ||
        (row.task_group !== undefined && !['overdue', 'today', 'remaining'].includes(row.task_group)))) throw new Error('브리핑 응답 형식을 확인해 주세요.')
}

export function briefingFromResults(results: { tool: string; data: Record<string, unknown> }[]): Briefing | null {
  const daily = results.find(r => r.tool === 'get_daily_briefing')
  if (daily) { checkBriefing(daily.data, daily.tool); return daily.data as unknown as Briefing }
  const weather = results.find(r => r.tool === 'get_weather')
  if (!weather) return null
  checkBriefing(weather.data, weather.tool)
  return { date: String(weather.data.date ?? ''), preview: weather.data.preview === true, weatherOnly: true,
    weather: weather.data as unknown as Weather, classes: [], tasks: [] }
}

// Preview only: deterministic examples do not pretend to be model interpretation.
export function previewKind(command: string): 'briefing' | 'weather' | null {
  if (/분석|피질|상관|뇌/.test(command)) return null
  if (/할\s*일|수업|일정|브리핑/.test(command)) return 'briefing'
  return /날씨/.test(command) ? 'weather' : null
}
