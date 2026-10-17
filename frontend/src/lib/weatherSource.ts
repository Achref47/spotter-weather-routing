import type { AnalyzeResponse } from '../types'

// Wording and rules that keep simulated weather visibly separate from the live forecast.
// Pure and import-light so `npm test` can cover it.

export const SIMULATED_BADGE = 'SIMULATED STORM · not a live forecast'
export const LIVE_SOURCE_NOTE = 'Weather: live forecast data from Open-Meteo.'

/** The label the backend puts at the start of its warnings for a simulated analysis. */
const DEMO_WARNING_PREFIX = 'SIMULATED STORM'

type WithSource = Pick<AnalyzeResponse, 'weather_source'>

export function isSimulated(result: WithSource | null): boolean {
  return result?.weather_source === 'demo'
}

/**
 * Warnings to list under the recommendation. The simulated-weather notice is dropped from the
 * list because the banner at the top of the results already shows it in full.
 */
export function visibleWarnings(result: Pick<AnalyzeResponse, 'weather_source' | 'warnings'>): string[] {
  return result.warnings.filter((w) => !(isSimulated(result) && w.startsWith(DEMO_WARNING_PREFIX)))
}

/** Checkpoint table heading, marked when the readings are simulated. */
export function checkpointHeading(routeLabel: string, simulated: boolean): string {
  return simulated ? `Checkpoints · ${routeLabel} · simulated weather` : `Checkpoints · ${routeLabel}`
}

/** Explanation under the heatmap slider. Starts with SIMULATED when the data is simulated. */
export function heatmapNote(hour: number, simulated: boolean): string {
  const base =
    `Forecast risk along the corridor at departure + ${hour} h (your local time), for your load ` +
    'weight. It is not tied to where the truck is: checkpoint risk on the route cards uses each ' +
    'route’s own arrival times.'
  return simulated ? `SIMULATED weather, not a forecast. ${base}` : base
}
