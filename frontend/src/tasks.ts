export interface TaskRecord { id: number; title: string; status: 'todo' | 'in_progress' | 'done'; planned_on: string | null; due_on: string | null; due_time: string | null; operation?: string }
export function isTaskTool(tool: string) { return tool === 'manage_tasks' || tool === 'list_tasks' || tool === 'register_courses' }
export function checkTaskResult(data: Record<string, unknown>, tool: string) {
  if (tool === 'register_courses') {
    if (data.kind !== 'course_changes' || typeof data.message !== 'string' ||
        !['saved', 'needs_input', 'cancelled', 'no_change'].includes(String(data.status)) ||
        !Array.isArray(data.items) || data.items.length > 10 || !Array.isArray(data.candidates) || data.candidates.length ||
        data.items.some(row => !row || !Number.isSafeInteger(row.id) || row.id < 1 || typeof row.name !== 'string' ||
          typeof row.semester_name !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(row.starts_on) || !/^\d{4}-\d{2}-\d{2}$/.test(row.ends_on) ||
          !Array.isArray(row.meetings) || !row.meetings.length || row.meetings.length > 20 || row.meetings.some((m: { weekday: number; starts_at: string; ends_at: string }) =>
            !m || !Number.isInteger(m.weekday) || m.weekday < 1 || m.weekday > 7 || !/^\d{2}:\d{2}(:\d{2})?$/.test(m.starts_at) || !/^\d{2}:\d{2}(:\d{2})?$/.test(m.ends_at)))) throw new Error('수업 등록 결과 형식을 확인해 주세요.')
    return
  }
  const date = (value: unknown) => value === null || (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value))
  const row = (value: unknown) => {
    const item = value as TaskRecord | null
    return item && Number.isSafeInteger(item.id) && item.id > 0 && typeof item.title === 'string' &&
      ['todo', 'in_progress', 'done'].includes(item.status) && date(item.planned_on) && date(item.due_on) &&
      (item.due_time === null || (typeof item.due_time === 'string' && /^\d{2}:\d{2}(:\d{2})?$/.test(item.due_time)))
  }
  if (data.kind !== (tool === 'manage_tasks' ? 'task_changes' : 'tasks') || typeof data.message !== 'string' ||
    !['saved', 'needs_input', 'cancelled', 'no_change', 'listed'].includes(String(data.status)) ||
    !Array.isArray(data.items) || data.items.length > 20 || !data.items.every(row) ||
    !Array.isArray(data.candidates) || data.candidates.length > 10 || !data.candidates.every(row)) throw new Error('할 일 처리 결과 형식을 확인해 주세요.')
}
