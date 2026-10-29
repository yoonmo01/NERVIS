import test from 'node:test'
import assert from 'node:assert/strict'
import { checkedReply, viewSelection, pending, interfaceState, correlationLabel } from '../src/conversation.ts'
import type { AIReply, LocalResult } from '../src/conversation.ts'
import { briefingFromResults, previewKind } from '../src/briefing.ts'

const result = (tool: string, parameters: Record<string, unknown>, data = {}): LocalResult => ({ result_id: tool, tool, parameters, data: { analysis: tool, dataset_version: 'v', ...data } })
const reply = (...results: LocalResult[]): AIReply => ({ status: 'ok', model_acknowledgement: '완료', results, warning: null })

test('briefing routes to home cards without brain selection or dataset version', () => {
  const data = { kind: 'briefing', preview: true, date: '2026-10-23', classes: [], tasks: [],
    weather: { status: 'not_configured', location: '춘천', current: null, hourly: [] } }
  const r: LocalResult = { result_id: 'brief', tool: 'get_daily_briefing', parameters: {}, data }
  const value = checkedReply(reply(r), 'v')
  assert.equal(viewSelection(value), null)
  assert.equal(briefingFromResults(value.results)?.preview, true)
  assert.equal(previewKind('hey NERVIS 오늘 할 일 알려줘'), 'briefing')
  assert.equal(previewKind('오늘 날씨 알려줘'), 'weather')
  assert.equal(previewKind('전전두피질 분석해줘'), null)
  assert.throws(() => checkedReply(reply({ ...r, data: { ...data, tasks: [{ title: null }] } }), 'v'))
})

test('single-region analysis preserves the explicit side and range without adding a partner', () => {
  const comparison = { regions: [{ label_id: 13 }], samples: [51], zscore: [[0]], correlation: null }
  const r = result('analyze_region', { region_id: 13, start: 51, end: 51 }, { comparison })
  const selection = viewSelection(checkedReply(reply(r), 'v'))!
  assert.equal(selection.region, 13)
  assert.equal(selection.single, true)
  assert.equal(selection.region_b, undefined)
  assert.equal(selection.start, 51)
  assert.equal(selection.end, 51)
  assert.equal(selection.comparison, comparison)
  assert.throws(() => viewSelection(reply(result('analyze_region', { region_id: 3, start: 80, end: 20 }))))
})

test('commands retain explicit pair, method, range and exact returned calculation', () => {
  const r = result('compare_regions', { region_a: 6, region_b: 16, start: 51, end: 150, method: 'spearman' })
  const selection = viewSelection(checkedReply(reply(r), 'v'))!
  assert.equal(selection.region, 6); assert.equal(selection.region_b, 16)
  assert.equal(selection.start, 51); assert.equal(selection.end, 150); assert.equal(selection.method, 'spearman')
  assert.equal(selection.comparison, r.data)
  const windows = viewSelection(reply(result('analyze_pair_over_windows', { region_a: 1, region_b: 2, start: 51, end: 150, window: 40, step: 5 })))!
  assert.equal(windows.window, 40); assert.equal(windows.step, 5); assert.equal(windows.region_b, 2)
})

test('ranking uses actual first computed pair and all region counts remain in results', () => {
  const r = reply(result('find_similar_pairs', { start: 21, end: 100 }, { pairs: [{ region_a: 8, region_b: 18, correlation: .2 }] }))
  assert.equal(viewSelection(r)?.region, 8); assert.equal(viewSelection(r)?.end, 100)
  assert.equal(viewSelection(reply(result('get_timeseries', { region_ids: [1, 2, 3] }))), null)
  assert.equal(viewSelection(reply(result('get_timeseries', { region_ids: [1, 11], start: 51, end: 52 }))), null)
  assert.equal(viewSelection(reply(result('get_dataset_summary', {}))), null)
})

test('a requested MRI recommendation is preserved for the analysis stage', () => {
  const slice = { orientation: 'Coronal', slice_index: 161, pixel_counts: { '6': 42 } }
  const selection = viewSelection(reply(result('get_region_slices', { region_id: 6, orientation: 'Coronal' }, { recommended_slice: slice })))!
  assert.equal(selection.region, 6)
  assert.equal(selection.recommendedSlice, slice)
})

test('bad versions, repeated IDs and invalid view parameters fail instead of changing the view', () => {
  const r = result('compare_regions', { region_a: 1, region_b: 11 })
  assert.throws(() => checkedReply(reply(r), 'other'))
  assert.throws(() => checkedReply(reply(r, r), 'v'))
  for (const p of [{ region_a: 1, region_b: 1 }, { region_a: 0, region_b: 11 }, { region_a: 1, region_b: 11, start: 150, end: 51 }]) {
    assert.throws(() => viewSelection(reply(result('compare_regions', p))))
  }
  assert.equal(pending('requesting'), true); assert.equal(pending('applying'), true)
  assert.equal(pending('error'), false); assert.equal(pending('complete'), false)
})

test('detailed results reuse their exact comparison and windows without changing pair or scope', () => {
  const comparison = { correlation: .3 }, windows = { windows: [] }
  const r = result('analyze_regions_detailed', { region_a: 6, region_b: 16, start: 51, end: 150, window: 40, step: 5 }, { comparison, windows })
  const selection = viewSelection(checkedReply(reply(r), 'v'))!
  assert.equal(selection.comparison, comparison); assert.equal(selection.windowResult, windows)
  assert.equal(selection.window, 40); assert.equal(selection.start, 51)
})

test('one state drives the orb and label and actual ranges label correlation', () => {
  assert.equal(interfaceState('requesting', true, true, false), 'processing')
  assert.equal(interfaceState('applying', true, true, false), 'analyzing')
  assert.equal(interfaceState('error', true, true, false), 'error')
  assert.equal(interfaceState('complete', true, true, false), 'standby')
  assert.equal(interfaceState('idle', true, false, false), 'paused')
  assert.equal(correlationLabel(1, 200, false), '전체 구간 1~200')
  assert.equal(correlationLabel(51, 150, false), '분석 구간 51~150')
  assert.equal(correlationLabel(51, 100, true), '이동 창 51~100')
})

test('task receipts and clarification stay out of brain selection and reject malformed records', () => {
  const packet: AIReply = { status: 'ok', warning: null, model_acknowledgement: '등록했습니다.', results: [
    { result_id: 'task', tool: 'manage_tasks', parameters: {}, data: { kind: 'task_changes', status: 'saved', message: '등록했습니다.', candidates: [], items: [
      { id: 1, title: '공모전 제출', status: 'todo', planned_on: null, due_on: '2026-10-29', due_time: null },
    ] } },
  ] }
  assert.equal(viewSelection(checkedReply(packet, 'v')), null)
  assert.throws(() => checkedReply({ ...packet, results: [{ ...packet.results[0], data: { ...packet.results[0].data, items: [{ id: -1, title: 'bad', status: 'made-up' }] } }] }, 'v'))
})

test('course registration receipt stays in conversation and validates timetable', () => {
  const data = { kind: 'course_changes', status: 'saved', message: '수업을 등록했습니다.', candidates: [], items: [
    { id: 1, name: '합성 AI', semester_name: '2026-2', starts_on: '2026-09-01', ends_on: '2026-12-20', meetings: [{ weekday: 1, starts_at: '09:00', ends_at: '10:15', location: null }] },
  ] }
  const packet: AIReply = { status: 'ok', warning: null, model_acknowledgement: data.message, results: [{ result_id: 'course', tool: 'register_courses', parameters: {}, data }] }
  assert.equal(viewSelection(checkedReply(packet, 'v')), null)
  assert.throws(() => checkedReply({ ...packet, results: [{ ...packet.results[0], data: { ...data, items: [{ ...data.items[0], meetings: [{ weekday: 8 }] }] } }] }, 'v'))
})
