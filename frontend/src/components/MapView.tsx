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
import {
  checkpointsCollection,
  emptyCollection,
  routeBounds,
  routesCollection,
} from '../lib/mapData'
import { checkpointPopup } from '../lib/popup'
import type { AnalyzeResponse, Place } from '../types'

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
}

function pin(label: 'A' | 'B', place: Place): HTMLElement {
  const el = document.createElement('div')
  el.className = 'pin'
  el.textContent = label
  el.title = place.label
  return el
}

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

export default function MapView({ result, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const markers = useRef<Marker[]>([])
  const onSelectRef = useRef(onSelect)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

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
      const checkpoint = map.queryRenderedFeatures(hitBox(e.point, 7), { layers: ['checkpoints'] })[0]
      if (checkpoint) {
        const [lon, lat] = (checkpoint.geometry as Point).coordinates
        new Popup({ maxWidth: '280px' })
          .setLngLat([lon, lat])
          .setDOMContent(checkpointPopup(checkpoint.properties ?? {}))
          .addTo(map)
        return
      }
      const route = map.queryRenderedFeatures(hitBox(e.point, 8), { layers: ['routes-other'] })[0]
      if (route) onSelectRef.current(String(route.properties?.id))
    })

    map.on('mousemove', (e) => {
      if (!map.getLayer('checkpoints')) return
      const hit = map.queryRenderedFeatures(hitBox(e.point, 6), {
        layers: ['checkpoints', 'routes-other'],
      })
      map.getCanvas().style.cursor = hit.length > 0 ? 'pointer' : ''
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
      {!result && <div className="map-hint">Enter a trip and click “Compare routes”.</div>}
    </>
  )
}