import type { AnalyzeRequest, Interval } from '../types'

// Turns the form fields into an analysis request, or says what is wrong. Pure, so `npm test`
// covers it. The limits mirror backend/trips/serializers.py; the server still re-checks them.

export const MAX_LOAD_LB = 80_000
export const MAX_DAYS_AHEAD = 7
const PAST_TOLERANCE_MS = 5 * 60 * 1000
const DAY_MS = 24 * 60 * 60 * 1000

export interface TripFormValues {
  origin: string
  destination: string
  /** The value of an <input type="datetime-local">, in the browser's local time. */
  departure: string
  loadLb: string
  interval: Interval
}

export type BuildResult = { ok: true; request: AnalyzeRequest } | { ok: false; error: string }

/** `demo` is 'storm' only when the user pressed the demo button; otherwise the request is live. */
export function buildRequest(
  values: TripFormValues,
  demo: 'storm' | undefined,
  now: Date = new Date(),
): BuildResult {
  const origin = values.origin.trim()
  const destination = values.destination.trim()
  if (origin.length < 2 || destination.length < 2) {
    return { ok: false, error: 'Enter an origin and a destination.' }
  }

  const when = new Date(values.departure)
  if (values.departure.trim() === '' || Number.isNaN(when.getTime())) {
    return { ok: false, error: 'Choose a departure date and time.' }
  }
  if (when.getTime() < now.getTime() - PAST_TOLERANCE_MS) {
    return { ok: false, error: 'The departure time is in the past. Choose a time from now onwards.' }
  }
  if (when.getTime() > now.getTime() + MAX_DAYS_AHEAD * DAY_MS) {
    return {
      ok: false,
      error: `Choose a departure within the next ${MAX_DAYS_AHEAD} days. Forecasts do not reach further.`,
    }
  }

  // An empty field would otherwise turn into 0 lb without the user noticing.
  const load = values.loadLb.trim() === '' ? Number.NaN : Number(values.loadLb)
  if (!Number.isFinite(load) || load < 0 || load > MAX_LOAD_LB) {
    return { ok: false, error: `Load weight must be between 0 and ${MAX_LOAD_LB.toLocaleString('en-US')} lb.` }
  }

  return {
    ok: true,
    request: {
      origin,
      destination,
      departure_time: when.toISOString().replace(/\.\d{3}Z$/, 'Z'),
      load_weight_lb: load,
      checkpoint_interval_mi: values.interval,
      demo_scenario: demo,
    },
  }
}
