import type { Map as MapLibreMap } from 'maplibre-gl'
import { riskColor } from './format'

export const HEATMAP_SOURCE = 'heatmap'
export const HEATMAP_LAYER = 'heatmap'

// Why circles and not MapLibre's "heatmap" layer: that layer paints point *density*, so a point
// with level 4 and a point with level 0 would only differ in weight, and the colour ramp cannot
// say "Severe" versus "No Travel". Wide, blurred circles coloured by the risk level blend into a
// smooth band along the corridor and keep every colour tied to a named level (see the legend).

/** Adds the heatmap source and layer, below the route lines so routes and dots stay on top. */
export function addHeatmapLayer(map: MapLibreMap, beforeLayerId: string): void {
  map.addSource(HEATMAP_SOURCE, {
    type: 'geojson',
    data: { type: 'FeatureCollection', features: [] },
  })
  map.addLayer(
    {
      id: HEATMAP_LAYER,
      type: 'circle',
      source: HEATMAP_SOURCE,
      paint: {
        'circle-color': riskColor(0),
        'circle-opacity': 0.3,
        // About 40 km on the ground once zoomed in: roughly the spacing between corridor points
        // (25 miles), so neighbours touch and form one band instead of separate dots. Zoomed out,
        // 40 km would shrink under the route dots, so the band never gets narrower than 14 px.
        'circle-radius': ['interpolate', ['exponential', 2], ['zoom'], 3, 14, 5.5, 14, 12, 1280],
        'circle-blur': 0.3,
        'circle-pitch-alignment': 'map',
      },
    },
    beforeLayerId,
  )
}

/**
 * Point the heatmap at forecast hour N. This only changes two paint properties: the data already
 * holds all 49 hours, so there is no network call and no data upload while the slider moves.
 */
export function applyHeatmapHour(map: MapLibreMap, hour: number, visible: boolean): void {
  if (!map.getLayer(HEATMAP_LAYER)) return
  map.setLayoutProperty(HEATMAP_LAYER, 'visibility', visible ? 'visible' : 'none')
  // Level 0 to 4, or -1 when no forecast was available.
  const level: ['number', ['at', number, ['array', ['get', string]]], number] = [
    'number',
    ['at', hour, ['array', ['get', 'levels']]],
    -1,
  ]
  map.setPaintProperty(HEATMAP_LAYER, 'circle-color', [
    'match',
    level,
    0, riskColor(0),
    1, riskColor(1),
    2, riskColor(2),
    3, riskColor(3),
    4, riskColor(4),
    riskColor(-1),
  ])
  // Calm weather stays faint so the risky stretches stand out.
  map.setPaintProperty(HEATMAP_LAYER, 'circle-opacity', [
    'match',
    level,
    0, 0.3,
    1, 0.5,
    2, 0.6,
    3, 0.7,
    4, 0.75,
    0.25,
  ])
}
