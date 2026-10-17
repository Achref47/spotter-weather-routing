import assert from 'node:assert/strict'
import { test } from 'node:test'
import { LOADING_TEXT, mapMessage } from './messages.ts'
import type { AnalyzeResponse } from '../types.ts'

// Only the field mapMessage reads. The cast keeps the fixtures short.
const withStatus = (status: string) =>
  ({ recommendation: { route_id: null, status, explanation: '' } }) as unknown as AnalyzeResponse

test('nothing analysed yet: tells the user how to start', () => {
  assert.match(mapMessage(null, false) ?? '', /Compare routes/)
})

test('a failed analysis explains that nothing can be shown', () => {
  assert.match(mapMessage(null, true) ?? '', /could not be analyzed/)
})

test('a failure wins over an older result that is still held', () => {
  assert.match(mapMessage(withStatus('recommended'), true) ?? '', /could not be analyzed/)
})

test('no safe route is flagged on the map', () => {
  assert.match(mapMessage(withStatus('no_safe_route'), false) ?? '', /No safe route/)
})

test('a normal result shows no message over the map', () => {
  assert.equal(mapMessage(withStatus('recommended'), false), null)
  assert.equal(mapMessage(withStatus('incomplete_data'), false), null)
})

test('the loading text no longer promises "up to 10 seconds"', () => {
  assert.doesNotMatch(LOADING_TEXT, /10 seconds/)
  assert.match(LOADING_TEXT, /5–15 seconds/)
})
