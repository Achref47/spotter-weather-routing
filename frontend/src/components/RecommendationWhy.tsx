import { buildWhy } from '../lib/recommendation'
import type { Recommendation, Route } from '../types'

interface Props {
  recommendation: Recommendation
  routes: Route[]
}

/** Explains the recommendation in the required order. Everything shown comes from the backend. */
export default function RecommendationWhy({ recommendation, routes }: Props) {
  const why = buildWhy(recommendation, routes)
  if (!why) return null

  return (
    <details className="why" open>
      <summary>Why this route?</summary>
      <p className="why-gate">{why.gate}</p>
      {why.intro && <p className="why-intro">{why.intro}</p>}
      {why.steps.length > 0 && (
        <ol className="why-steps">
          {why.steps.map((step) => (
            <li key={step.key} className={`why-step ${step.outcome}`}>
              <span className="why-label">{step.label}</span>
              <span className="why-values">
                {step.best} <span className="why-vs">vs</span> {step.runner_up}
              </span>
              <span className="why-outcome">{step.outcomeText}</span>
            </li>
          ))}
        </ol>
      )}
    </details>
  )
}
