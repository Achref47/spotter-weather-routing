import { useRef, useState } from 'react'
import './App.css'
import { analyzeTrip } from './api'
import CheckpointTable from './components/CheckpointTable'
import MapView from './components/MapView'
import RouteList from './components/RouteList'
import TripForm from './components/TripForm'
import { checkpointKey } from './lib/checkpoints'
import { LOADING_TEXT } from './lib/messages'
import type { AnalyzeRequest, AnalyzeResponse, Checkpoint, FocusRequest, Route } from './types'

const BANNER_CLASS: Record<string, string> = {
  recommended: 'good',
  incomplete_data: 'warn',
  no_safe_route: 'danger',
  no_routes: 'warn',
}

export default function App() {
  const [result, setResult] = useState<AnalyzeResponse | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [focus, setFocus] = useState<FocusRequest | null>(null)
  const controller = useRef<AbortController | null>(null)

  async function handleSubmit(request: AnalyzeRequest) {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeTrip(request, current.signal)
      setResult(data)
      setFocus(null)
      setSelectedId(data.recommendation.route_id ?? data.routes[0]?.id ?? null)
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return
      setResult(null)
      setError(e instanceof Error ? e.message : 'Something went wrong.')
    } finally {
      if (controller.current === current) setLoading(false)
    }
  }

  function focusCheckpoint(route: Route, checkpoint: Checkpoint) {
    setFocus({ routeId: route.id, mile: checkpoint.mile })
  }

  const selectedRoute = result?.routes.find((r) => r.id === selectedId) ?? null

  return (
    <div className="app">
      <aside className="panel">
        <h1>Weather-Aware Truck Routing</h1>
        <TripForm onSubmit={handleSubmit} loading={loading} />

        {error && (
          <p className="banner danger" role="alert">
            {error}
          </p>
        )}
        {loading && (
          <p className="banner info" role="status">
            {LOADING_TEXT}
          </p>
        )}

        {result && !loading && (
          <>
            <p className={`banner ${BANNER_CLASS[result.recommendation.status] ?? 'info'}`}>
              <strong>
                {result.recommendation.status === 'no_safe_route' ? 'No safe route available. ' : ''}
              </strong>
              {result.recommendation.explanation}
            </p>
            {result.warnings.map((w) => (
              <p key={w} className="banner warn">
                {w}
              </p>
            ))}
            <RouteList
              routes={result.routes}
              recommendation={result.recommendation}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
            {selectedRoute && (
              <CheckpointTable
                route={selectedRoute}
                focusedKey={focus ? checkpointKey(focus.routeId, focus.mile) : null}
                onFocus={focusCheckpoint}
              />
            )}
          </>
        )}

        <footer className="credits">
          Routes © Mapbox, © OpenStreetMap contributors · Geocoding: Nominatim, ©{' '}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">
            OpenStreetMap contributors
          </a>{' '}
          · Weather data by{' '}
          <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">
            Open-Meteo.com
          </a>
        </footer>
      </aside>

      <main className="map-area">
        <MapView
          result={result}
          selectedId={selectedId}
          onSelect={setSelectedId}
          loading={loading}
          failed={error !== null}
          focus={focus}
        />
      </main>
    </div>
  )
}