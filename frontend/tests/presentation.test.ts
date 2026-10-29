import test from 'node:test'
import assert from 'node:assert/strict'
import { presentationSegments, presentationTargets, briefingCue, briefingPlaybackStage, previewSegments } from '../src/presentation.ts'
import type { AIReply } from '../src/conversation.ts'
import type { LocalResult } from '../src/conversation.ts'
import type { Briefing } from '../src/briefing.ts'

test('dynamic segments preserve the answer and reject invented or stale targets', () => {
  const reply = { model_acknowledgement: '오늘은 발표를 준비하세요.', results: [{ tool: 'list_tasks', data: { items: [{}] } }],
    segments: [{ text: '오늘은 발표를 준비하세요.', target: 'r0.tasks.0' }] } as unknown as AIReply
  assert.deepEqual(presentationSegments(reply), reply.segments)
  assert.equal(briefingCue('r0.tasks.0'), 'tasks')
  assert.equal(briefingCue('response'), 'overview')
  reply.segments = [{ text: '잘못된 문장', target: 'r0.tasks.0' }]
  assert.deepEqual(presentationSegments(reply), [])
  reply.segments = [{ text: reply.model_acknowledgement!, target: 'r0.tasks.1' }]
  assert.deepEqual(presentationSegments(reply), [])
})

test('targets exclude undisplayed duplicate results and completed briefing tasks', () => {
  const result = (tool: string, data = {}): LocalResult => ({ tool, data, parameters: {}, result_id: tool })
  const task = result('list_tasks', { items: [{}] })
  assert.equal(presentationTargets([task, task]).has('r1.tasks.0'), false)
  const weather = result('get_weather')
  const daily = result('get_daily_briefing', { classes: [], tasks: [{ status: 'done' }, { status: 'todo' }] })
  const targets = presentationTargets([weather, daily])
  assert.equal(targets.has('r0.weather'), false)
  assert.equal(targets.has('r1.tasks.0'), false)
  assert.equal(targets.has('r1.tasks.1'), true)
  assert.deepEqual([...presentationTargets([weather, result('analyze_region')])], ['response'])
})

test('synthetic preview narration carries the same dynamic contract as an AI answer', () => {
  const value = { weather: { location: '춘천', current: { temperature_c: 18 } }, classes: [{ course_name: '합성 수업', starts_at: '09:00' }], tasks: [{ title: '합성 할 일' }] } as Briefing
  const segments = previewSegments(value, false)
  const reply = { model_acknowledgement: segments.map(s => s.text).join(' '), segments,
    results: [{ tool: 'get_daily_briefing', data: value }] } as unknown as AIReply
  assert.deepEqual(presentationSegments(reply), segments)
  assert.ok(segments.some(s => s.target === 'r0.tasks.0' && s.text.includes('합성 할 일')))
})

test('cards wait for playback, follow current result cues and dock on stop, failure or reduced motion', () => {
  assert.equal(briefingPlaybackStage({ active: true }, 'r0', false, false), 'waiting')
  assert.equal(briefingPlaybackStage({ active: true, target: 'r0.classes.0' }, 'r0', false, false), 'classes')
  assert.equal(briefingPlaybackStage({ active: true, target: 'r1.tasks' }, 'r0', false, false), 'overview')
  assert.equal(briefingPlaybackStage({ active: false, target: 'r0.tasks' }, 'r0', false, false), 'docked')
  assert.equal(briefingPlaybackStage({ active: true, target: 'r0.tasks' }, 'r0', true, false), 'docked')
  assert.equal(briefingPlaybackStage({ active: true, target: 'r0.tasks' }, 'r0', false, true), 'docked')
})
