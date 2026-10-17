import type { Feature, FeatureCollection, Point } from 'geojson'
import type { Heatmap } from '../types'

// Pure helpers for the forecast heatmap. They import only types, so they run under
// `npm test` (Node's built-in test runner) without a browser or extra dependencies.

const HOUR_MS = 3_600_000

/** A whole slider hour between 0 and maxHour. Anything that is not a number becomes 0. */
export function clampHour(hour: number, maxHour: number): number {
  if (!Number.isFinite(hour)) return 0
  const top = Number.isFinite(maxHour) ? Math.max(0, Math.floor(maxHour)) : 0
  return Math.min(Math.max(Math.round(hour), 0), top)
}

/**
 * One point per corridor location. The 49 hourly levels (0 to 4, or -1 for unknown) stay on the
 * feature, so moving the slider only changes which entry the map style reads. Nothing is re-sent.
 */
export function heatmapCollection(heatmap: Heatmap): FeatureCollection<Point> {
  const features: Feature<Point>[] = heatmap.points.map((p) => ({
    type: 'Feature',
    properties: { levels: p.levels },
    geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
  }))
  return { type: 'FeatureCollection', features }
}

/** "+N h": how many hours after departure the slider is showing. */
export function hourOffsetLabel(hour: number): string {
  return `+${hour} h`
}

/** Clock time for departure + N hours, e.g. "Sun, Oct 18, 03:00 PM" in the viewer's time zone. */
export function hourClock(startIso: string, hour: number, locale?: string, timeZone?: string): string {
  const when = new Date(Date.parse(startIso) + hour * HOUR_MS)
  return when.toLocaleString(locale, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  })
}
