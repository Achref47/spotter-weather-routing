import assert from 'node:assert/strict'
import { test } from 'node:test'
import { clampHour, heatmapCollection, hourClock, hourOffsetLabel } from './heatmap.ts'
import type { Heatmap } from '../types.ts'

// Newer ICU versions put a no-break space before AM/PM. \s matches it, so compare with plain spaces.
const plain = (s: string) => s.replace(/\s/g, ' ')

const START = '2026-10-18T14:00:00+00:00'

test('clampHour keeps the slider between 0 and the last hour', () => {
  assert.equal(clampHour(-3, 48), 0)
  assert.equal(clampHour(0, 48), 0)
  assert.equal(clampHour(48, 48), 48)
  assert.equal(clampHour(49, 48), 48)
  assert.equal(clampHour(12.4, 48), 12)
  assert.equal(clampHour(Number.NaN, 48), 0)
  assert.equal(clampHour(5, Number.NaN), 0)
})

test('hourOffsetLabel shows hours after departure', () => {
  assert.equal(hourOffsetLabel(0), '+0 h')
  assert.equal(hourOffsetLabel(48), '+48 h')
})

test('hourClock is departure plus N hours', () => {
  assert.equal(plain(hourClock(START, 0, 'en-US', 'UTC')), 'Sun, Oct 18, 02:00 PM')
  assert.equal(plain(hourClock(START, 1, 'en-US', 'UTC')), 'Sun, Oct 18, 03:00 PM')
})

test('hourClock rolls over midnight and reaches +48 h', () => {
  assert.equal(plain(hourClock(START, 11, 'en-US', 'UTC')), 'Mon, Oct 19, 01:00 AM')
  assert.equal(plain(hourClock(START, 48, 'en-US', 'UTC')), 'Tue, Oct 20, 02:00 PM')
})

test('hourClock follows the viewer time zone', () => {
  assert.equal(plain(hourClock(START, 0, 'en-US', 'America/Chicago')), 'Sun, Oct 18, 09:00 AM')
})

test('heatmapCollection keeps coordinates in lon,lat order and every hourly level', () => {
  const levels = Array.from({ length: 49 }, (_, i) => (i % 5) - 1)
  const heatmap: Heatmap = {
    start_time: START,
    hours: 48,
    legend: {},
    points: [
      { lat: 29.76, lon: -95.37, levels },
      { lat: 33.75, lon: -84.39, levels: levels.map(() => 4) },
    ],
  }
  const collection = heatmapCollection(heatmap)
  assert.equal(collection.features.length, 2)
  assert.deepEqual(collection.features[0].geometry.coordinates, [-95.37, 29.76])
  assert.deepEqual(collection.features[0].properties, { levels })
  assert.equal((collection.features[1].properties?.levels as number[]).length, 49)
})

test('heatmapCollection of an empty heatmap is an empty collection', () => {
  const empty: Heatmap = { start_time: START, hours: 48, legend: {}, points: [] }
  assert.deepEqual(heatmapCollection(empty).features, [])
})
