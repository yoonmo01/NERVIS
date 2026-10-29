import assert from 'node:assert/strict'
import test from 'node:test'
import { answerMarkdown } from '../src/answerMarkdown.ts'

test('repairs escaped paired bold without altering ordinary markdown or code', () => {
  assert.equal(answerMarkdown(String.raw`비 확률 \*\*60%\*\*, **오늘** 8\~9°C`), String.raw`비 확률 **60%**, **오늘** 8\~9°C`)
  const code = '`\\*\\*literal\\*\\*`\n```\n\\*\\*literal\\*\\*\n```'
  assert.equal(answerMarkdown(code), code)
  assert.equal(answerMarkdown(String.raw`별표 \* 하나`), String.raw`별표 \* 하나`)
})

test('bold Korean names ending in parentheses have a closing delimiter boundary', () => {
  assert.equal(answerMarkdown('**전전두피질(왼쪽)**과 **운동피질(왼쪽)**의 신호'), '**전전두피질(왼쪽)** 과 **운동피질(왼쪽)** 의 신호')
  assert.equal(answerMarkdown('`**전전두피질(왼쪽)**과`'), '`**전전두피질(왼쪽)**과`')
})
