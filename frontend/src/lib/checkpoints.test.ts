import assert from 'node:assert/strict'
import { test } from 'node:test'
import { checkpointKey, etaShort, formatMile, formatReading } from './checkpoints.ts'

// Newer ICU versions put a no-break space before AM/PM. \s matches it, so compare with plain spaces.
const plain = (s: string) => s.replace(/\s/g, ' ')

test('formatMile shows whole miles plainly and the final partial mile with one decimal', () => {
  assert.equal(formatMile(0), '0')
  assert.equal(formatMile(25), '25')
  assert.equal(formatMile(794.4), '794.4')
  assert.equal(formatMile(794.44), '794.4')
})

test('formatReading never turns a missing value into zero', () => {
  assert.equal(formatReading(null, 1), '—')
  assert.equal(formatReading(0, 1), '0.0')
  assert.equal(formatReading(12.34, 1), '12.3')
  assert.equal(formatReading(0.126, 2), '0.13')
})

test('etaShort gives weekday and clock time in the requested time zone', () => {
  const iso = '2026-10-18T14:00:00+00:00'
  assert.equal(plain(etaShort(iso, 'en-US', 'UTC')), 'Sun 02:00 PM')
  assert.equal(plain(etaShort(iso, 'en-US', 'America/Chicago')), 'Sun 09:00 AM')
})

test('etaShort changes weekday across midnight', () => {
  assert.equal(plain(etaShort('2026-10-18T23:30:00+00:00', 'en-US', 'UTC')), 'Sun 11:30 PM')
  assert.equal(plain(etaShort('2026-10-19T00:30:00+00:00', 'en-US', 'UTC')), 'Mon 12:30 AM')
})

test('checkpointKey is unique per route and mile', () => {
  assert.equal(checkpointKey('route-1', 25), 'route-1:25')
  assert.notEqual(checkpointKey('route-1', 25), checkpointKey('route-2', 25))
  assert.notEqual(checkpointKey('route-1', 25), checkpointKey('route-1', 50))
})
