import test from 'node:test'
import assert from 'node:assert/strict'
import { weatherMessage, weatherTime } from '../src/weather.ts'

test('weather distinguishes missing, unknown, partial and unavailable states', () => {
  assert.match(weatherMessage('not_configured'), /인증키/)
  assert.match(weatherMessage('unknown_location'), /지원/)
  assert.match(weatherMessage('partial'), /일부/)
  assert.match(weatherMessage('unavailable'), /가져오지/)
  assert.equal(weatherMessage('ok'), '')
})
test('weather time is displayed in Korea time and missing time is not invented', () => {
  assert.equal(weatherTime(null), '—')
  assert.equal(weatherTime('invalid'), '—')
  assert.match(weatherTime('2026-10-23T10:00:00Z'), /19:00/)
})
