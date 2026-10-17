import assert from 'node:assert/strict'
import { test } from 'node:test'
import { toLocalInputValue } from './format.ts'
import { buildRequest, MAX_DAYS_AHEAD, type TripFormValues } from './tripRequest.ts'

const NOW = new Date('2026-10-17T12:00:00Z')
const HOUR = 3_600_000
const MINUTE = 60_000
const DAY = 24 * HOUR

// A departure `ms` after NOW, written the way a datetime-local input writes it (local time).
const departureIn = (ms: number) => toLocalInputValue(new Date(NOW.getTime() + ms))

const valid = (over: Partial<TripFormValues> = {}): TripFormValues => ({
  origin: 'Houston, TX',
  destination: 'Atlanta, GA',
  departure: departureIn(HOUR),
  loadLb: '42000',
  interval: 25,
  ...over,
})

const errorOf = (values: TripFormValues) => {
  const result = buildRequest(values, undefined, NOW)
  assert.equal(result.ok, false)
  return result.ok ? '' : result.error
}

test('a valid form builds a live request: trimmed text, numeric load, UTC time without milliseconds', () => {
  const result = buildRequest(valid({ origin: '  Houston, TX ', destination: 'Atlanta, GA  ' }), undefined, NOW)
  assert.ok(result.ok)
  const r = result.request
  assert.equal(r.origin, 'Houston, TX')
  assert.equal(r.destination, 'Atlanta, GA')
  assert.equal(r.load_weight_lb, 42000)
  assert.equal(r.checkpoint_interval_mi, 25)
  assert.match(r.departure_time, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/)
  assert.equal(r.demo_scenario, undefined)
})

test('the departure time round-trips to the same moment (the user typed local time)', () => {
  const values = valid({ departure: departureIn(5 * HOUR + 30 * MINUTE) })
  const result = buildRequest(values, undefined, NOW)
  assert.ok(result.ok)
  assert.equal(new Date(result.request.departure_time).getTime(), new Date(values.departure).getTime())
})

test('only the demo button sets the demo scenario', () => {
  const live = buildRequest(valid(), undefined, NOW)
  const demo = buildRequest(valid(), 'storm', NOW)
  assert.ok(live.ok && demo.ok)
  assert.equal(live.request.demo_scenario, undefined)
  assert.equal(demo.request.demo_scenario, 'storm')
  assert.ok(!('demo_scenario' in JSON.parse(JSON.stringify(live.request)))) // omitted from the JSON body
})

test('origin and destination must have at least 2 characters', () => {
  assert.equal(errorOf(valid({ origin: 'H' })), 'Enter an origin and a destination.')
  assert.equal(errorOf(valid({ destination: '   ' })), 'Enter an origin and a destination.')
  assert.ok(buildRequest(valid({ origin: 'LA', destination: 'NY' }), undefined, NOW).ok)
})

test('a missing or garbled departure is rejected', () => {
  assert.equal(errorOf(valid({ departure: '' })), 'Choose a departure date and time.')
  assert.equal(errorOf(valid({ departure: 'tomorrow' })), 'Choose a departure date and time.')
})

test('a departure in the past is rejected, with the same 5 minute grace as the server', () => {
  assert.match(errorOf(valid({ departure: departureIn(-1 * HOUR) })), /in the past/)
  assert.ok(buildRequest(valid({ departure: departureIn(-4 * MINUTE) }), undefined, NOW).ok)
  assert.match(errorOf(valid({ departure: departureIn(-10 * MINUTE) })), /in the past/)
})

test('a departure more than 7 days ahead is rejected, 6 days is fine', () => {
  assert.ok(buildRequest(valid({ departure: departureIn(6 * DAY) }), undefined, NOW).ok)
  assert.match(errorOf(valid({ departure: departureIn((MAX_DAYS_AHEAD + 1) * DAY) })), /next 7 days/)
})

test('load weight must be a number from 0 to 80,000 lb', () => {
  for (const bad of ['', '   ', 'abc', '-1', '80001', 'NaN', 'Infinity']) {
    assert.equal(errorOf(valid({ loadLb: bad })), 'Load weight must be between 0 and 80,000 lb.', bad)
  }
  for (const good of ['0', '80000', '42000.5', ' 30000 ']) {
    assert.ok(buildRequest(valid({ loadLb: good }), undefined, NOW).ok, good)
  }
})

test('an empty load field is an error, not silently 0 lb', () => {
  const result = buildRequest(valid({ loadLb: '' }), undefined, NOW)
  assert.equal(result.ok, false)
})

test('the first problem is reported when several fields are wrong', () => {
  assert.equal(
    errorOf(valid({ origin: '', departure: '', loadLb: 'x' })),
    'Enter an origin and a destination.',
  )
})

test('each checkpoint interval is passed through', () => {
  for (const interval of [10, 25, 50] as const) {
    const result = buildRequest(valid({ interval }), undefined, NOW)
    assert.ok(result.ok)
    assert.equal(result.request.checkpoint_interval_mi, interval)
  }
})
