import {
    AttributionControl,
    Map as MapLibreMap,
    Marker,
    NavigationControl,
    Popup,
    setWorkerUrl,
    type GeoJSONSource,
} from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { Point } from 'geojson'
import { useEffect, useRef, useState } from 'react'
import { riskColor } from '../lib/format'
import { heatmapCollection } from '../lib/heatmap'
import { addHeatmapLayer, applyHeatmapHour, HEATMAP_SOURCE } from '../lib/heatmapStyle'
import {
  checkpointsCollection,
  emptyCollection,
  routeBounds,
  routesCollection,
} from '../lib/mapData'
import { checkpointPopup } from '../lib/popup'
import type { AnalyzeResponse, Place } from '../types'
import HeatmapControl from './HeatmapControl'

setWorkerUrl(workerUrl)
const STYLE_URL: string =
  import.meta.env.VITE_MAP_STYLE ?? 'https://tiles.openfreemap.org/styles/liberty'

const LEGEND: [number, string][] = [
  [0, 'Low'],
  [1, 'Moderate'],
  [2, 'High'],
  [3, 'Severe'],
  [4, 'No Travel'],
  [-1, 'Unknown'],
]

interface Props {
  result: AnalyzeResponse | null
  selectedId: string | null
  onSelect: (id: string) => void
  loading: boolean
  failed: boolean
}

/** The message shown over the map when there is nothing to draw, or something to flag. */
function mapMessage(result: AnalyzeResponse | null, failed: boolean): string | null {
  if (failed) return 'The trip could not be analyzed. Fix the problem on the left and try again.'
  if (!result) return 'Enter a trip and click “Compare routes”.'
  if (result.recommendation.status === 'no_safe_route') {
    return 'No safe route: every route has No Travel conditions at this departure time.'
  }
  return null
}

function pin(label: 'A' | 'B', place: Place): HTMLElement {
  const el = document.createElement('div')
  el.className = 'pin'
  el.textContent = label
  el.title = place.label
  return el
}

// Checkpoints can be only ~19 px apart on screen, so dots get a tight hit area. Any larger and
// the dots would cover the route lines, and clicking a line to select it would never work.
const DOT_HIT_PAD = 2
const ROUTE_HIT_PAD = 8

function hitBox(point: { x: number; y: number }, pad: number): [[number, number], [number, number]] {
  return [
    [point.x - pad, point.y - pad],
    [point.x + pad, point.y + pad],
  ]
}

function addLayers(map: MapLibreMap) {
  map.addSource('routes', { type: 'geojson', data: emptyCollection() })
  map.addSource('checkpoints', { type: 'geojson', data: emptyCollection() })

  map.addLayer({
    id: 'routes-other',
    type: 'line',
    source: 'routes',
    filter: ['!=', ['get', 'id'], ''],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-width': 4, 'line-opacity': 0.55 },
  })
  map.addLayer({
    id: 'routes-selected-casing',
    type: 'line',
    source: 'routes',
    filter: ['==', ['get', 'id'], ''],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#ffffff', 'line-width': 9, 'line-opacity': 0.9 },
  })
  map.addLayer({
    id: 'routes-selected',
    type: 'line',
    source: 'routes',
    filter: ['==', ['get', 'id'], ''],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': ['get', 'color'], 'line-width': 6 },
  })
  map.addLayer({
    id: 'checkpoints',
    type: 'circle',
    source: 'checkpoints',
    paint: {
      'circle-color': ['get', 'color'],
      'circle-radius': 3.5,
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 1.5,
    },
  })
  addHeatmapLayer(map, 'routes-other')
}

function applySelection(map: MapLibreMap, selectedId: string | null) {
  const id = selectedId ?? ''
  map.setFilter('routes-other', ['!=', ['get', 'id'], id])
  map.setFilter('routes-selected-casing', ['==', ['get', 'id'], id])
  map.setFilter('routes-selected', ['==', ['get', 'id'], id])
  map.setPaintProperty('checkpoints', 'circle-radius', [
    'case',
    ['==', ['get', 'routeId'], id],
    6,
    3.5,
  ])
  map.setPaintProperty('checkpoints', 'circle-opacity', [
    'case',
    ['==', ['get', 'routeId'], id],
    1,
    0.65,
  ])
  map.setLayoutProperty('checkpoints', 'circle-sort-key', [
    'case',
    ['==', ['get', 'routeId'], id],
    1,
    0,
  ])
}

export default function MapView({ result, selectedId, onSelect, loading, failed }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markers = useRef<Marker[]>([])
  const onSelectRef = useRef(onSelect)
  const selectedRef = useRef(selectedId)
  const [ready, setReady] = useState(false)
  const [heatVisible, setHeatVisible] = useState(true)
  // The slider hour belongs to one result; a new result starts again at hour 0.
  const [heatHour, setHeatHour] = useState<{ forResult: AnalyzeResponse | null; hour: number }>({
    forResult: null,
    hour: 0,
  })
  const hour = heatHour.forResult === result ? heatHour.hour : 0

  useEffect(() => {
    onSelectRef.current = onSelect
    selectedRef.current = selectedId
  }, [onSelect, selectedId])

  // Create the map once.
  useEffect(() => {
    if (!container.current) return
    const map = new MapLibreMap({
      container: container.current,
      style: STYLE_URL,
      center: [-96, 38],
      zoom: 3.4,
      attributionControl: false,
    })
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(
      new AttributionControl({
        compact: false,
        customAttribution: 'Routes © Mapbox · Weather data by Open-Meteo.com',
      }),
    )

    map.on('load', () => {
      addLayers(map)
      setReady(true)
    })

    map.on('click', (e) => {
      if (!map.getLayer('checkpoints')) return
      const checkpoint = map.queryRenderedFeatures(hitBox(e.point, DOT_HIT_PAD), {
        layers: ['checkpoints'],
      })[0]
      if (checkpoint) {
        // A dot of another route selects that route; a dot of the selected route shows its details.
        const routeId = String(checkpoint.properties?.routeId)
        if (routeId !== selectedRef.current) {
          onSelectRef.current(routeId)
          return
        }
        const [lon, lat] = (checkpoint.geometry as Point).coordinates
        new Popup({ maxWidth: '280px' })
          .setLngLat([lon, lat])
          .setDOMContent(checkpointPopup(checkpoint.properties ?? {}))
          .addTo(map)
        return
      }
      const route = map.queryRenderedFeatures(hitBox(e.point, ROUTE_HIT_PAD), {
        layers: ['routes-other'],
      })[0]
      if (route) onSelectRef.current(String(route.properties?.id))
    })
    map.on('error', (e) => {
      console.error('MapLibre error:', e.error?.message ?? e)
    })

    map.on('mousemove', (e) => {
      if (!map.getLayer('checkpoints')) return
      const overDot = map.queryRenderedFeatures(hitBox(e.point, DOT_HIT_PAD), {
        layers: ['checkpoints'],
      })
      const overRoute = map.queryRenderedFeatures(hitBox(e.point, ROUTE_HIT_PAD), {
        layers: ['routes-other'],
      })
      map.getCanvas().style.cursor = overDot.length + overRoute.length > 0 ? 'pointer' : ''
    })

    mapRef.current = map
    return () => {
      setReady(false)
      map.remove()
      mapRef.current = null
    }
  }, [])

  // New results: update the data, the A/B pins and the view.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    const routes = result?.routes ?? []

    const routeSource = map.getSource('routes') as GeoJSONSource | undefined
    const checkpointSource = map.getSource('checkpoints') as GeoJSONSource | undefined
    routeSource?.setData(routesCollection(routes))
    checkpointSource?.setData(checkpointsCollection(routes))
    const heatSource = map.getSource(HEATMAP_SOURCE) as GeoJSONSource | undefined
    heatSource?.setData(result ? heatmapCollection(result.heatmap) : emptyCollection())

    markers.current.forEach((m) => m.remove())
    markers.current = []
    if (result) {
      markers.current = [
        new Marker({ element: pin('A', result.origin) })
          .setLngLat([result.origin.lon, result.origin.lat])
          .addTo(map),
        new Marker({ element: pin('B', result.destination) })
          .setLngLat([result.destination.lon, result.destination.lat])
          .addTo(map),
      ]
      const bounds = routeBounds(result.routes)
      if (bounds) map.fitBounds(bounds, { padding: 60, duration: 800 })
    }
  }, [ready, result])

  // Selection changes only touch filters and styles, so they are instant.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    applySelection(map, selectedId)
  }, [ready, selectedId])

  // Moving the slider only changes two paint properties on the map. No data, no network.
  useEffect(() => {
    const map = mapRef.current
    if (!ready || !map) return
    applyHeatmapHour(map, hour, heatVisible)
  }, [ready, hour, heatVisible])

  const message = mapMessage(result, failed)

  return (
    <>
      <div className="map-canvas" ref={container} aria-label="Route map" />
      <div className="legend" aria-label="Risk legend">
        {LEGEND.map(([level, name]) => (
          <div key={name}>
            <span className="dot" style={{ background: riskColor(level) }} aria-hidden="true" />
            {name}
          </div>
        ))}
      </div>
      {result && result.heatmap.points.length > 0 && !loading && (
        <HeatmapControl
          heatmap={result.heatmap}
          hour={hour}
          onHour={(h) => setHeatHour({ forResult: result, hour: h })}
          visible={heatVisible}
          onVisible={setHeatVisible}
        />
      )}
      {message && !loading && <div className="map-hint">{message}</div>}
      {loading && (
        <div className="map-loading" aria-hidden="true">
          <span className="spinner" />
          Analyzing routes and weather…
        </div>
      )}
    </>
  )
}