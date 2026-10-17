import type { AnalyzeResponse } from '../types'
import { buildWhy } from './recommendation.ts'

// Builds the downloadable CSV trip report from an analysis the backend already produced.
// It only READS the response: it never ranks, classifies or recomputes risk, and it does not
// modify its input. Pure and DOM-free, so `npm test` covers it. The download itself lives in
// download.ts.
//
// Conventions
//  - Every timestamp in the file is UTC, ISO 8601 (e.g. 2026-10-20T08:00:00Z), and the column or
//    row label says "(UTC)". The "Report generated" row is when the file was downloaded; the
//    "Departure" row is when the trip leaves. They are different things.
//  - Missing or unknown readings are written as the word "unknown", never as 0.
//  - Rows end in CRLF (RFC 4180). The spreadsheet BOM is added by withBom().

export const SIMULATED_REPORT_BANNER = 'SIMULATED STORM \u2014 NOT A LIVE FORECAST'
export const UNKNOWN = 'unknown'
export const NO_RECOMMENDATION = 'No route is safely recommended'
const BOM = '\uFEFF'
const EOL = '\r\n'

/** A number is written as-is. A string is untrusted text: it gets formula protection. */
export type Cell = string | number | null | undefined

// Characters that make a spreadsheet read a text cell as a formula (OWASP), plus tab and CR,
// which some programs strip before looking at the first character.
const FORMULA_START = /^[=+\-@\t\r]/

/**
 * One CSV field. Numbers are written untouched, so a negative number is not altered. Text that
 * could start a formula is prefixed with an apostrophe FIRST, and quoting is applied to the
 * result, so the two protections combine correctly.
 */
export function csvCell(value: Cell): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : UNKNOWN
  let text = value
  if (FORMULA_START.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

export function csvRow(cells: Cell[]): string {
  return cells.map(csvCell).join(',')
}

/** Prepends the byte-order mark Excel needs to read UTF-8 correctly. */
export function withBom(csv: string): string {
  return BOM + csv
}

/** A UTC timestamp without milliseconds. A value that is not a date is kept as it was given. */
export function isoUtc(value: string): string {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

function hoursMinutes(seconds: number): string {
  const total = Math.round(seconds / 60)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** A reading in its own unit, or "unknown". Never 0 for a missing value. */
function reading(value: number | null): Cell {
  return value === null || value === undefined ? UNKNOWN : value
}

export function isSimulatedResult(result: Pick<AnalyzeResponse, 'weather_source'>): boolean {
  return result.weather_source === 'demo'
}

/** Filename with a UTC timestamp. A simulated analysis always carries SIMULATED-STORM. */
export function reportFilename(
  result: Pick<AnalyzeResponse, 'weather_source'>,
  generatedAt: Date,
): string {
  const stamp = generatedAt.toISOString().replace(/\.\d{3}Z$/, 'Z').replace(/[-:]/g, '')
  const kind = isSimulatedResult(result) ? '-SIMULATED-STORM' : ''
  return `spotter-trip-report${kind}-${stamp}.csv`
}

export function buildReportCsv(result: AnalyzeResponse, generatedAt: Date): string {
  const simulated = isSimulatedResult(result)
  const rows: Cell[][] = []
  const blank = () => rows.push([])

  // A. Header. The simulated banner is the very first line of the file.
  if (simulated) {
    rows.push([SIMULATED_REPORT_BANNER])
    blank()
  }
  rows.push(['Spotter \u2014 Weather-Aware Truck Routing: trip report'])
  rows.push(['Report generated (UTC)', isoUtc(generatedAt.toISOString())])
  rows.push([
    'Forecast data source',
    simulated
      ? 'Simulated storm (deterministic demonstration; no forecast data was used)'
      : 'Open-Meteo live forecast',
  ])
  rows.push([
    'Analysis type',
    simulated ? 'SIMULATED (not a live forecast)' : 'Live analysis',
  ])
  rows.push(['Time zone of all timestamps', 'UTC'])
  blank()

  // B. Trip summary.
  const rec = result.recommendation
  const recommended = result.routes.find((r) => r.id === rec.route_id)
  rows.push(['TRIP SUMMARY'])
  rows.push(['Origin', result.origin.label])
  rows.push(['Destination', result.destination.label])
  rows.push(['Departure (UTC)', isoUtc(result.departure_time)])
  rows.push(['Load weight', `${result.load_weight_lb} lb`])
  rows.push(['Checkpoint interval', `${result.checkpoint_interval_mi} mi`])
  rows.push([
    'Recommended route',
    recommended ? `${recommended.label} (${recommended.id})` : NO_RECOMMENDATION,
  ])
  rows.push(['Recommendation status', rec.status])
  rows.push(['Why this route', rec.explanation])
  // The structured trail the "Why this route?" panel already shows. Nothing is re-ranked here.
  const why = buildWhy(rec, result.routes)
  if (why) {
    rows.push(['Safety gate', why.gate])
    if (why.intro) rows.push(['Comparison', why.intro])
    if (why.steps.length > 0) {
      blank()
      rows.push(['Criterion', 'Recommended route', 'Runner-up', 'Outcome'])
      for (const s of why.steps) rows.push([s.label, s.best, s.runner_up, s.outcomeText])
    }
  }
  blank()

  // C. Route comparison.
  rows.push(['ROUTE COMPARISON'])
  rows.push([
    'Route ID',
    'Route',
    'Recommended',
    'Rank',
    'Distance (mi)',
    'Duration (min)',
    'Duration (h:mm)',
    'ETA (UTC)',
    'No Travel (mi)',
    'Severe (mi)',
    'High (mi)',
    'Unknown weather (mi)',
    'Average risk (0-4)',
  ])
  for (const r of result.routes) {
    const s = r.summary
    rows.push([
      r.id,
      r.label,
      r.id === rec.route_id ? 'yes' : 'no',
      r.rank,
      r.distance_mi,
      Math.round(r.duration_s / 60),
      hoursMinutes(r.duration_s),
      isoUtc(r.arrival_time),
      s.no_travel_mi,
      s.severe_mi,
      s.high_mi,
      s.unknown_mi,
      reading(s.avg_risk),
    ])
  }
  rows.push([
    'Average risk is distance-weighted over miles with known weather on a scale of 0 to 4: ' +
      '0 Low, 1 Moderate, 2 High, 3 Severe, 4 No Travel. "unknown" means no known miles.',
  ])
  blank()

  // D. Checkpoint details for every route.
  rows.push(['CHECKPOINT DETAILS'])
  rows.push([
    'Route ID',
    'Route',
    'Mile (mi)',
    'ETA (UTC)',
    'Wind (mph)',
    'Rain (in/hr)',
    'Snow (in/hr)',
    'Risk level',
  ])
  for (const r of result.routes) {
    for (const c of r.checkpoints) {
      rows.push([
        r.id,
        r.label,
        c.mile,
        isoUtc(c.eta),
        reading(c.weather.wind_mph),
        reading(c.weather.rain_in_hr),
        reading(c.weather.snow_in_hr),
        c.risk.overall ?? UNKNOWN,
      ])
    }
  }

  return rows.map(csvRow).join(EOL) + EOL
}
