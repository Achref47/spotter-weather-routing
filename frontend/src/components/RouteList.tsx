import { avgRiskLabel, formatDateTime, formatDuration, formatMiles, routeColor } from '../lib/format'
import type { Recommendation, Route } from '../types'

interface Props {
  routes: Route[]
  recommendation: Recommendation
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function RouteList({ routes, recommendation, selectedId, onSelect }: Props) {
  const ordered = [...routes].sort((a, b) => a.rank - b.rank)

  return (
    <ul className="routes">
      {ordered.map((route) => {
        const s = route.summary
        const selected = route.id === selectedId
        return (
          <li key={route.id}>
            <button
              type="button"
              className={`route-card${selected ? ' selected' : ''}`}
              aria-pressed={selected}
              onClick={() => onSelect(route.id)}
            >
              <div className="route-head">
                <span className="swatch" style={{ background: routeColor(route.id) }} aria-hidden="true" />
                <span className="rank">#{route.rank}</span>
                <strong>{route.label}</strong>
                {route.id === recommendation.route_id && <span className="badge good">Recommended</span>}
                {s.no_travel_mi > 0 && <span className="badge danger">No Travel</span>}
              </div>
              <div className="route-meta">
                {formatMiles(route.distance_mi)} mi · {formatDuration(route.duration_s)} · arrives{' '}
                {formatDateTime(route.arrival_time)}
              </div>
              <dl className="stats">
                <div>
                  <dt>Severe</dt>
                  <dd>{formatMiles(s.severe_mi)} mi</dd>
                </div>
                <div>
                  <dt>High</dt>
                  <dd>{formatMiles(s.high_mi)} mi</dd>
                </div>
                <div>
                  <dt>No Travel</dt>
                  <dd>{formatMiles(s.no_travel_mi)} mi</dd>
                </div>
                <div>
                  <dt>Avg risk</dt>
                  <dd>{avgRiskLabel(s.avg_risk)}</dd>
                </div>
              </dl>
              {s.unknown_mi > 0 && (
                <p className="note">{formatMiles(s.unknown_mi)} mi without forecast data</p>
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}