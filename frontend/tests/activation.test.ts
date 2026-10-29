import assert from 'node:assert/strict'
import test from 'node:test'
import { DoubleClap, isWakePhrase } from '../src/activation.ts'

test('wake requires both the greeting and NERVIS name', () => {
  for (const text of ['Hey NERVIS!', '헤이 너비스', '헤이 네르비스']) assert.equal(isWakePhrase(text), true)
  for (const text of ['오늘 할 일 알려줘', 'NERVIS', '헤이', 'maybe nervis']) assert.equal(isWakePhrase(text), false)
})

test('two brief separated bursts trigger, one or long noise does not', () => {
  const detector = new DoubleClap()
  assert.equal(detector.feed(.2, .8, 0), false)
  assert.equal(detector.feed(.001, .01, 80), false)
  assert.equal(detector.feed(.2, .8, 350), false)
  assert.equal(detector.feed(.001, .01, 430), true)
  const noise = new DoubleClap()
  noise.feed(.2, .8, 0); noise.feed(.2, .8, 300)
  assert.equal(noise.feed(.001, .01, 380), false)
  noise.feed(.2, .8, 600)
  assert.equal(noise.feed(.001, .01, 680), false)
})
