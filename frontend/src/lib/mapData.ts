import type { Feature, FeatureCollection, LineString, Point } from 'geojson'
import type { Checkpoint, Route } from '../types'
import { formatDateTime, riskColor, riskTextColor, routeColor } from './format'

export type Bounds = [[number, number], [number, number]]

export function emptyCollection(): FeatureCollection {
  return { type: 'FeatureCollection', features: [] }
}

export function routesCollection(routes: Route[]): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: routes.map((r) => ({
      type: 'Feature',
      properties: { id: r.id, color: routeColor(r.id) },
      geometry: r.geometry,
    })),
  }
}

function describe(value: number | null, unit: string, digits: number): string {
  return value === null ? 'unavailable' : `${value.toFixed(digits)} ${unit}`
}

/** What the checkpoint popup shows. Used for map features and for the table's "focus" action. */
export function checkpointProperties(route: Route, c: Checkpoint): Record<string, string | number> {
  return {
    routeId: route.id,
    routeLabel: route.label,
    mile: c.mile,
    eta: formatDateTime(c.eta),
    wind: describe(c.weather.wind_mph, 'mph', 1),
    rain: describe(c.weather.rain_in_hr, 'in/hr', 2),
    snow: describe(c.weather.snow_in_hr, 'in/hr', 2),
    risk: c.risk.overall ?? 'Unknown',
    color: riskColor(c.risk.overall_level),
    textColor: riskTextColor(c.risk.overall_level),
    reasons: c.risk.reasons.join('|'),
  }
}

export function checkpointsCollection(routes: Route[]): FeatureCollection<Point> {
  const features: Feature<Point>[] = []
  for (const r of routes) {
    for (const c of r.checkpoints) {
      features.push({
        type: 'Feature',
        properties: checkpointProperties(r, c),
        geometry: { type: 'Point', coordinates: [c.lon, c.lat] },
      })
    }
  }
  return { type: 'FeatureCollection', features }
}

export function routeBounds(routes: Route[]): Bounds | null {
  let minLon = Infinity
  let minLat = Infinity
  let maxLon = -Infinity
  let maxLat = -Infinity
  for (const r of routes) {
    for (const [lon, lat] of r.geometry.coordinates) {
      if (lon < minLon) minLon = lon
      if (lon > maxLon) maxLon = lon
      if (lat < minLat) minLat = lat
      if (lat > maxLat) maxLat = lat
    }
  }
  return Number.isFinite(minLon)
    ? [
        [minLon, minLat],
        [maxLon, maxLat],
      ]
    : null
}