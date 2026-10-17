import type { CriterionStep, Recommendation, Route } from '../types'

// Builds the "Why this route?" explanation from what the backend decided. It never ranks or
// compares routes itself, so it cannot disagree with the recommendation. Pure and import-light
// so `npm test` covers the wording.

export interface WhyView {
  /** What the No Travel safety gate did. It always runs before the four criteria. */
  gate: string
  /** Sentence introducing the criteria, or null when there was nothing to compare. */
  intro: string | null
  /** The four criteria in the required order, each tied, decisive or not needed. */
  steps: (CriterionStep & { outcomeText: string })[]
}

const OUTCOME_TEXT: Record<CriterionStep['outcome'], string> = {
  decisive: 'Decides it',
  tied: 'Tied',
  not_needed: 'Not needed',
}

export function outcomeText(outcome: CriterionStep['outcome']): string {
  return OUTCOME_TEXT[outcome]
}

function listExcluded(excluded: { label: string; no_travel_mi: number }[]): string {
  return excluded.map((e) => `${e.label} (${e.no_travel_mi.toFixed(1)} mi)`).join(', ')
}

/** Null when there is nothing worth explaining beyond the recommendation banner. */
export function buildWhy(recommendation: Recommendation, routes: Route[]): WhyView | null {
  const cmp = recommendation.comparison
  if (!cmp || routes.length < 2) return null

  const best = routes.find((r) => r.id === recommendation.route_id)
  const excludedText = listExcluded(cmp.excluded)

  let gate: string
  if (recommendation.status === 'no_safe_route') {
    gate = `Every route has No Travel conditions, so none can be recommended. No Travel miles: ${excludedText}.`
  } else if (cmp.excluded.length > 0) {
    gate = `The safety gate removes any route with No Travel miles before anything else is compared. Excluded: ${excludedText}.`
  } else {
    gate = 'No route has No Travel conditions, so the safety gate removed nothing.'
  }

  let intro: string | null = null
  if (cmp.trail.length > 0 && best && cmp.runner_up_label) {
    intro = `${best.label} and ${cmp.runner_up_label} are compared on these criteria in this order. The first one that is not tied decides.`
  } else if (best && recommendation.status !== 'no_safe_route') {
    intro = `${best.label} is the only route that passed the safety gate, so no further comparison was needed.`
  }

  return {
    gate,
    intro,
    steps: cmp.trail.map((step) => ({ ...step, outcomeText: outcomeText(step.outcome) })),
  }
}
