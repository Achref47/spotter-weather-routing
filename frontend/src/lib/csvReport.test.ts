import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildReportCsv,
  csvCell,
  csvRow,
  isoUtc,
  NO_RECOMMENDATION,
  reportFilename,
  SIMULATED_REPORT_BANNER,
  UNKNOWN,
  withBom,
} from './csvReport.ts'
import type { AnalyzeResponse, Checkpoint, Route } from '../types'

const GENERATED = new Date('2026-10-17T15:02:47.123Z')

function checkpoint(mile: number, wind: number | null, overall: Checkpoint['risk']['overall']): Checkpoint {
  return {
    mile,
    lat: 30,
    lon: -95,
    eta: '2026-10-20T09:30:00+00:00',
    weather: { wind_mph: wind, rain_in_hr: wind === null ? null : 0, snow_in_hr: wind === null ? null : 0 },
    risk: {
      wind: overall,
      rain: overall,
      snow: overall,
      overall,
      overall_level: overall === null ? null : 0,
      complete: wind !== null,
      reasons: [],
    },
  }
}

function route(id: string, rank: number, avg: number | null): Route {
  return {
    id,
    label: id === 'route-1' ? 'Fastest route' : 'Alternative route',
    source: 'alternative',
    distance_mi: 801.4,
    duration_s: 45_300,
    arrival_time: '2026-10-21T04:35:00+00:00',
    geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] },
    checkpoints: [checkpoint(0, 12.3, 'Low'), checkpoint(25, null, null)],
    summary: {
      low_mi: 700,
      moderate_mi: 0,
      high_mi: 1.5,
      severe_mi: 0.4,
      no_travel_mi: 0,
      unknown_mi: 25,
      avg_risk: avg,
      incomplete_checkpoints: 1,
    },
    rank,
  }
}

function result(overrides: Partial<AnalyzeResponse> = {}): AnalyzeResponse {
  return {
    origin: { label: 'Houston, Texas, USA', lat: 29.7, lon: -95.3 },
    destination: { label: 'Atlanta, Georgia, USA', lat: 33.7, lon: -84.4 },
    departure_time: '2026-10-20T08:00:00+00:00',
    load_weight_lb: 42000,
    checkpoint_interval_mi: 25,
    weather_source: 'live',
    demo: null,
    routes: [route('route-1', 1, 0.25), route('route-2', 2, null)],
    recommendation: {
      route_id: 'route-1',
      status: 'recommended',
      explanation: 'Fastest route ranks first on Fewest Severe miles (0.4 mi vs 1.0 mi).',
      comparison: {
        runner_up_id: 'route-2',
        runner_up_label: 'Alternative route',
        excluded: [],
        trail: [
          { key: 'severe_miles', label: 'Fewest Severe miles', best: '0.4 mi', runner_up: '1.0 mi', outcome: 'decisive' },
          { key: 'high_miles', label: 'Fewest High miles', best: '1.5 mi', runner_up: '2.0 mi', outcome: 'not_needed' },
          { key: 'average_risk', label: 'Lowest average risk', best: '0.25', runner_up: 'n/a', outcome: 'not_needed' },
          { key: 'travel_time', label: 'Shortest travel time', best: '12.6 h', runner_up: '12.6 h', outcome: 'not_needed' },
        ],
      },
    },
    heatmap: { start_time: '2026-10-20T08:00:00+00:00', hours: 48, legend: {}, points: [] },
    warnings: [],
    ...overrides,
  }
}

const simulated = () =>
  result({
    weather_source: 'demo',
    demo: { id: 'storm', label: 'SIMULATED STORM', description: 'd', how_to_read: [] },
  })

function lines(csv: string): string[] {
  return csv.split('\r\n')
}

test('fields with commas, quotes and newlines are quoted, and quotes are doubled', () => {
  assert.equal(csvCell('a,b'), '"a,b"')
  assert.equal(csvCell('say "hi"'), '"say ""hi"""')
  assert.equal(csvCell('line1\nline2'), '"line1\nline2"')
  assert.equal(csvCell('line1\r\nline2'), '"line1\r\nline2"')
  assert.equal(csvCell('plain'), 'plain')
  assert.equal(csvRow(['a', 'b,c', 3]), 'a,"b,c",3')
})

test('text starting with = + - @ (or tab / CR) is neutralised with a leading apostrophe', () => {
  for (const bad of ['=SUM(A1)', '+1', '-2', '@cmd', '\t=1', '\r=1']) {
    assert.ok(csvCell(bad).replace(/^"/, '').startsWith("'"), `${JSON.stringify(bad)} must be prefixed`)
  }
  assert.equal(csvCell('=1+1'), "'=1+1")
  assert.equal(csvCell('fine = ok'), 'fine = ok')
})

test('formula protection and quoting work together', () => {
  assert.equal(csvCell('=HYPERLINK("http://x","y"),z'), '"\'=HYPERLINK(""http://x"",""y""),z"')
})

test('typed numbers are not altered, including negative ones', () => {
  assert.equal(csvCell(-5), '-5')
  assert.equal(csvCell(0), '0')
  assert.equal(csvCell(12.3), '12.3')
  assert.equal(csvCell('-5'), "'-5") // the same value as untrusted TEXT is protected
  assert.equal(csvCell(Number.NaN), UNKNOWN)
})

test('a hostile place name cannot start a formula in the report', () => {
  const evil = result({ origin: { label: '=cmd|\' /C calc\'!A1', lat: 0, lon: 0 } })
  const row = lines(buildReportCsv(evil, GENERATED)).find((l) => l.startsWith('Origin,'))
  assert.ok(row?.startsWith("Origin,'="), row)
})

test('column headings carry their units', () => {
  const csv = buildReportCsv(result(), GENERATED)
  for (const heading of [
    'Distance (mi)',
    'Duration (min)',
    'ETA (UTC)',
    'No Travel (mi)',
    'Severe (mi)',
    'High (mi)',
    'Average risk (0-4)',
    'Mile (mi)',
    'Wind (mph)',
    'Rain (in/hr)',
    'Snow (in/hr)',
  ]) {
    assert.ok(csv.includes(heading), `missing heading ${heading}`)
  }
  assert.ok(csv.includes('Load weight,42000 lb'))
  assert.ok(csv.includes('Checkpoint interval,25 mi'))
})

test('a simulated report starts with the exact banner; a live report has no banner', () => {
  const sim = buildReportCsv(simulated(), GENERATED)
  assert.equal(lines(sim)[0], 'SIMULATED STORM \u2014 NOT A LIVE FORECAST')
  assert.equal(SIMULATED_REPORT_BANNER, 'SIMULATED STORM \u2014 NOT A LIVE FORECAST')
  assert.ok(sim.includes('SIMULATED (not a live forecast)'))
  assert.ok(!sim.includes('Open-Meteo live forecast'))

  const live = buildReportCsv(result(), GENERATED)
  assert.ok(!live.includes('SIMULATED'))
  assert.ok(live.includes('Open-Meteo live forecast'))
  assert.ok(lines(live)[0].startsWith('Spotter'))
})

test('the filename marks simulated reports and uses the UTC generation time', () => {
  assert.equal(reportFilename(result(), GENERATED), 'spotter-trip-report-20261017T150247Z.csv')
  assert.equal(
    reportFilename(simulated(), GENERATED),
    'spotter-trip-report-SIMULATED-STORM-20261017T150247Z.csv',
  )
})

test('generation time and departure time are separate rows, both in UTC', () => {
  const csv = buildReportCsv(result(), GENERATED)
  assert.ok(csv.includes('Report generated (UTC),2026-10-17T15:02:47Z'))
  assert.ok(csv.includes('Departure (UTC),2026-10-20T08:00:00Z'))
  assert.equal(isoUtc('2026-10-20T10:00:00+02:00'), '2026-10-20T08:00:00Z')
  assert.equal(isoUtc('not a date'), 'not a date')
})

test('unknown readings are written as "unknown", never as 0', () => {
  const csv = buildReportCsv(result(), GENERATED)
  // checkpoint with no weather: wind, rain, snow and risk level all unknown
  assert.ok(csv.includes('route-1,Fastest route,25,2026-10-20T09:30:00Z,unknown,unknown,unknown,unknown'))
  // route-2 has no average risk
  const row = lines(csv).find((l) => l.startsWith('route-2,Alternative route,no,2,'))
  assert.ok(row?.endsWith(',unknown'), row)
  // a known 0 reading stays 0
  assert.ok(csv.includes('route-1,Fastest route,0,2026-10-20T09:30:00Z,12.3,0,0,Low'))
})

test('with no safe route the report says so instead of naming a route', () => {
  const none = result({
    recommendation: {
      route_id: null,
      status: 'no_safe_route',
      explanation: 'No safe route is available.',
      comparison: {
        runner_up_id: null,
        runner_up_label: null,
        trail: [],
        excluded: [{ id: 'route-1', label: 'Fastest route', no_travel_mi: 3 }],
      },
    },
  })
  const csv = buildReportCsv(none, GENERATED)
  assert.ok(csv.includes(`Recommended route,${NO_RECOMMENDATION}`))
  assert.ok(csv.includes('Recommendation status,no_safe_route'))
  assert.ok(!csv.includes(',yes,'))
})

test('the "Why this route" explanation and criteria trail are exported as the UI shows them', () => {
  const csv = buildReportCsv(result(), GENERATED)
  assert.ok(csv.includes('Fewest Severe miles,0.4 mi,1.0 mi,Decides it'))
  assert.ok(csv.includes('Shortest travel time,12.6 h,12.6 h,Not needed'))
  assert.ok(csv.includes('Why this route,Fastest route ranks first on Fewest Severe miles (0.4 mi vs 1.0 mi).'))
})

test('the BOM is added once, only by withBom', () => {
  const csv = buildReportCsv(result(), GENERATED)
  assert.ok(!csv.startsWith('\uFEFF'))
  assert.ok(withBom(csv).startsWith('\uFEFF'))
  assert.equal(withBom(csv).slice(1), csv)
})

test('building a report does not change the analysis, ranking or recommendation', () => {
  const data = result()
  const snapshot = structuredClone(data)
  buildReportCsv(data, GENERATED)
  buildReportCsv(data, GENERATED)
  assert.deepEqual(data, snapshot)

  // A deep-frozen input proves nothing is written, even by accident.
  const frozen = structuredClone(data)
  const freeze = (o: unknown): void => {
    if (o && typeof o === 'object' && !Object.isFrozen(o)) {
      Object.freeze(o)
      Object.values(o).forEach(freeze)
    }
  }
  freeze(frozen)
  assert.doesNotThrow(() => buildReportCsv(frozen, GENERATED))
  assert.deepEqual(frozen.routes.map((r) => [r.id, r.rank]), [['route-1', 1], ['route-2', 2]])
})

test('the same input always gives the same file', () => {
  assert.equal(buildReportCsv(result(), GENERATED), buildReportCsv(result(), GENERATED))
})
