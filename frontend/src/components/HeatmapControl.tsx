import { clampHour, hourClock, hourOffsetLabel } from '../lib/heatmap'
import type { Heatmap } from '../types'

interface Props {
  heatmap: Heatmap
  hour: number
  onHour: (hour: number) => void
  visible: boolean
  onVisible: (visible: boolean) => void
}

/** The 0 to 48 hour forecast slider. Moving it never calls the server. */
export default function HeatmapControl({ heatmap, hour, onHour, visible, onVisible }: Props) {
  const clock = hourClock(heatmap.start_time, hour)
  const offset = hourOffsetLabel(hour)

  return (
    <section className="heat-control" aria-label="Weather forecast heatmap">
      <div className="heat-head">
        <label className="heat-toggle">
          <input type="checkbox" checked={visible} onChange={(e) => onVisible(e.target.checked)} />
          Weather heatmap
        </label>
        <output className="heat-time" htmlFor="heat-hour">
          <strong>{offset}</strong> · {clock}
        </output>
      </div>
      <input
        id="heat-hour"
        className="heat-slider"
        type="range"
        min={0}
        max={heatmap.hours}
        step={1}
        value={hour}
        disabled={!visible}
        aria-label="Forecast hour after departure"
        aria-valuetext={`${offset}, ${clock}`}
        onChange={(e) => onHour(clampHour(Number(e.target.value), heatmap.hours))}
      />
      <div className="heat-scale" aria-hidden="true">
        <span>Departure</span>
        <span>+{heatmap.hours} h</span>
      </div>
      <p className="heat-note">
        Forecast risk along the corridor at departure + {offset.replace('+', '')} (your local time),
        for your load weight. It is not tied to where the truck is: checkpoint risk on the route
        cards uses each route’s own arrival times.
      </p>
    </section>
  )
}
