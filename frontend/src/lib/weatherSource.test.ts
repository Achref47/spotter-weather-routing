import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  checkpointHeading,
  heatmapNote,
  isSimulated,
  LIVE_SOURCE_NOTE,
  SIMULATED_BADGE,
  visibleWarnings,
} from './weatherSource.ts'

const demo = { weather_source: 'demo' as const, warnings: [] as string[] }
const live = { weather_source: 'live' as const, warnings: [] as string[] }

test('only an explicit demo response counts as simulated', () => {
  assert.equal(isSimulated(demo), true)
  assert.equal(isSimulated(live), false)
  assert.equal(isSimulated(null), false)
})

test('the badge and live note say what the data is', () => {
  assert.match(SIMULATED_BADGE, /SIMULATED/)
  assert.match(SIMULATED_BADGE, /not a live forecast/)
  assert.match(LIVE_SOURCE_NOTE, /live forecast/)
})

test('the simulated notice is removed from the warning list, other warnings stay', () => {
  const warnings = [
    'SIMULATED STORM: demonstration weather, not a live forecast. Do not use it to judge real conditions.',
    'Only 2 distinct route(s) could be found for this trip.',
  ]
  assert.deepEqual(visibleWarnings({ ...demo, warnings }), [warnings[1]])
})

test('a live analysis never hides a warning, even one that starts with the same words', () => {
  const warnings = ['SIMULATED STORM text from somewhere else', 'Weather data was unavailable at some checkpoints.']
  assert.deepEqual(visibleWarnings({ ...live, warnings }), warnings)
})

test('the checkpoint heading is marked only for simulated weather', () => {
  assert.equal(checkpointHeading('Fastest route', false), 'Checkpoints · Fastest route')
  assert.equal(
    checkpointHeading('Fastest route', true),
    'Checkpoints · Fastest route · simulated weather',
  )
})

test('the heatmap note starts with SIMULATED only for simulated weather', () => {
  assert.ok(heatmapNote(3, true).startsWith('SIMULATED weather, not a forecast.'))
  assert.ok(!heatmapNote(3, false).includes('SIMULATED'))
  assert.match(heatmapNote(3, false), /departure \+ 3 h/)
})
