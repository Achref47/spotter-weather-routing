import type { AnalyzeResponse } from '../types'

// User-facing wording for the analysis states. Pure and import-light so `npm test` can cover it.

/** Shown while an analysis runs. Measured cold runs for a long trip take about 9 to 14 seconds. */
export const LOADING_TEXT = 'Fetching routes and weather forecasts… this usually takes 5–15 seconds.'

/** The message shown over the map when there is nothing to draw, or something to flag. */
export function mapMessage(result: AnalyzeResponse | null, failed: boolean): string | null {
  if (failed) return 'The trip could not be analyzed. Fix the problem on the left and try again.'
  if (!result) return 'Enter a trip and click “Compare routes”.'
  if (result.recommendation.status === 'no_safe_route') {
    return 'No safe route: every route has No Travel conditions at this departure time.'
  }
  return null
}
