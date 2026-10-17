import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildWhy, outcomeText } from './recommendation.ts'
import type { CriterionStep, Recommendation, Route } from '../types.ts'

const route = (id: string, label: string) => ({ id, label }) as unknown as Route
const ROUTES = [route('route-1', 'Fastest route'), route('route-2', 'Alternative route')]

const step = (
  key: CriterionStep['key'],
  label: string,
  outcome: CriterionStep['outcome'],
): CriterionStep => ({ key, label, best: '0.0 mi', runner_up: '5.0 mi', outcome })

const TRAIL: CriterionStep[] = [
  step('severe_miles', 'Fewest Severe miles', 'tied'),
  step('high_miles', 'Fewest High miles', 'tied'),
  step('average_risk', 'Lowest average risk', 'tied'),
  step('travel_time', 'Shortest travel time', 'decisive'),
]

type Comparison = NonNullable<Recommendation['comparison']>

const rec = (over: Partial<Recommendation>, cmp: Partial<Comparison> = {}): Recommendation => ({
  route_id: 'route-1',
  status: 'recommended',
  explanation: '',
  comparison: {
    runner_up_id: 'route-2',
    runner_up_label: 'Alternative route',
    trail: TRAIL,
    excluded: [],
    ...cmp,
  },
  ...over,
})

test('the four criteria appear in the required order, with their outcomes', () => {
  const view = buildWhy(rec({}), ROUTES)
  assert.ok(view)
  assert.deepEqual(
    view.steps.map((s) => s.label),
    ['Fewest Severe miles', 'Fewest High miles', 'Lowest average risk', 'Shortest travel time'],
  )
  assert.deepEqual(
    view.steps.map((s) => s.outcomeText),
    ['Tied', 'Tied', 'Tied', 'Decides it'],
  )
})

test('the intro names both routes and says the first untied criterion decides', () => {
  const view = buildWhy(rec({}), ROUTES)
  assert.match(view?.intro ?? '', /Fastest route and Alternative route/)
  assert.match(view?.intro ?? '', /first one that is not tied decides/)
})

test('with nothing excluded the gate says it removed nothing', () => {
  assert.equal(
    buildWhy(rec({}), ROUTES)?.gate,
    'No route has No Travel conditions, so the safety gate removed nothing.',
  )
})

test('excluded routes are named with their No Travel miles, and the gate is said to run first', () => {
  const view = buildWhy(
    rec(
      {},
      {
        excluded: [
          { id: 'route-3', label: 'Alternate corridor', no_travel_mi: 125 },
          { id: 'route-9', label: 'Coast route', no_travel_mi: 50.04 },
        ],
      },
    ),
    ROUTES,
  )
  assert.match(view?.gate ?? '', /before anything else is compared/)
  assert.match(view?.gate ?? '', /Excluded: Alternate corridor \(125\.0 mi\), Coast route \(50\.0 mi\)\./)
})

test('when only one route passed the gate there is no criteria list', () => {
  const view = buildWhy(
    rec(
      {},
      {
        runner_up_id: null,
        runner_up_label: null,
        trail: [],
        excluded: [{ id: 'route-2', label: 'Alternative route', no_travel_mi: 20 }],
      },
    ),
    ROUTES,
  )
  assert.equal(view?.steps.length, 0)
  assert.match(view?.intro ?? '', /only route that passed the safety gate/)
  assert.match(view?.gate ?? '', /Alternative route \(20\.0 mi\)/)
})

test('when every route is No Travel nothing is recommended and no comparison is claimed', () => {
  const view = buildWhy(
    rec(
      { route_id: null, status: 'no_safe_route' },
      {
        runner_up_id: null,
        runner_up_label: null,
        trail: [],
        excluded: [
          { id: 'route-1', label: 'Fastest route', no_travel_mi: 30 },
          { id: 'route-2', label: 'Alternative route', no_travel_mi: 10 },
        ],
      },
    ),
    ROUTES,
  )
  assert.match(view?.gate ?? '', /Every route has No Travel conditions, so none can be recommended/)
  assert.equal(view?.intro, null)
  assert.equal(view?.steps.length, 0)
})

test('nothing is shown for a single route or when the backend sent no comparison', () => {
  assert.equal(buildWhy(rec({}), [ROUTES[0]]), null)
  assert.equal(buildWhy(rec({ comparison: null }), ROUTES), null)
})

test('outcome wording does not rely on colour', () => {
  assert.equal(outcomeText('decisive'), 'Decides it')
  assert.equal(outcomeText('tied'), 'Tied')
  assert.equal(outcomeText('not_needed'), 'Not needed')
})
