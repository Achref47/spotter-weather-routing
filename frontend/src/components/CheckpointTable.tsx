import { checkpointKey, etaShort, formatMile, formatReading } from '../lib/checkpoints'
import { riskColor, riskTextColor } from '../lib/format'
import type { Checkpoint, Route } from '../types'

interface Props {
  route: Route
  focusedKey: string | null
  onFocus: (route: Route, checkpoint: Checkpoint) => void
}

/** Every weather checkpoint of the selected route. Clicking a mile zooms the map to it. */
export default function CheckpointTable({ route, focusedKey, onFocus }: Props) {
  return (
    <section className="cp-table" aria-labelledby="cp-table-title">
      <h2 id="cp-table-title">
        Checkpoints · {route.label}
        <span className="cp-count">{route.checkpoints.length}</span>
      </h2>
      <p className="cp-hint">
        Forecast at each checkpoint for the time this route reaches it. Choose a mile to zoom the map
        there.
      </p>
      <div className="cp-scroll" role="region" aria-label="Checkpoint table" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th scope="col">Mile</th>
              <th scope="col">ETA</th>
              <th scope="col">Risk</th>
              <th scope="col">
                Wind <small>mph</small>
              </th>
              <th scope="col">
                Rain <small>in/hr</small>
              </th>
              <th scope="col">
                Snow <small>in/hr</small>
              </th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((c) => {
              const key = checkpointKey(route.id, c.mile)
              const level = c.risk.overall_level
              return (
                <tr key={key} className={key === focusedKey ? 'focused' : undefined}>
                  <td>
                    <button
                      type="button"
                      className="cp-mile"
                      aria-label={`Show mile ${formatMile(c.mile)} on the map`}
                      onClick={() => onFocus(route, c)}
                    >
                      {formatMile(c.mile)}
                    </button>
                  </td>
                  <td>{etaShort(c.eta)}</td>
                  <td>
                    <span
                      className="risk-pill"
                      title={c.risk.reasons.join('\n')}
                      style={{ background: riskColor(level), color: riskTextColor(level) }}
                    >
                      {c.risk.overall ?? 'Unknown'}
                    </span>
                  </td>
                  <td>{formatReading(c.weather.wind_mph, 1)}</td>
                  <td>{formatReading(c.weather.rain_in_hr, 2)}</td>
                  <td>{formatReading(c.weather.snow_in_hr, 2)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
