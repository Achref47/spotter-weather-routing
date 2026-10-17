export type Interval = 10 | 25 | 50

export type RiskName = 'Low' | 'Moderate' | 'High' | 'Severe' | 'No Travel'

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface CheckpointWeather {
  wind_mph: number | null
  rain_in_hr: number | null
  snow_in_hr: number | null
}

export interface CheckpointRisk {
  wind: RiskName | null
  rain: RiskName | null
  snow: RiskName | null
  overall: RiskName | null
  overall_level: number | null
  complete: boolean
  reasons: string[]
}

export interface Checkpoint {
  mile: number
  lat: number
  lon: number
  eta: string
  weather: CheckpointWeather
  risk: CheckpointRisk
}

export interface RouteSummary {
  low_mi: number
  moderate_mi: number
  high_mi: number
  severe_mi: number
  no_travel_mi: number
  unknown_mi: number
  avg_risk: number | null
  incomplete_checkpoints: number
}

export interface Route {
  id: string
  label: string
  source: string
  distance_mi: number
  duration_s: number
  arrival_time: string
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  checkpoints: Checkpoint[]
  summary: RouteSummary
  rank: number
}

export interface Recommendation {
  route_id: string | null
  status: 'recommended' | 'incomplete_data' | 'no_safe_route' | 'no_routes'
  explanation: string
}

export interface HeatmapPoint {
  lat: number
  lon: number
  levels: number[]
}

export interface Heatmap {
  start_time: string
  hours: number
  legend: Record<string, string>
  points: HeatmapPoint[]
}

export interface AnalyzeResponse {
  origin: Place
  destination: Place
  departure_time: string
  load_weight_lb: number
  checkpoint_interval_mi: number
  routes: Route[]
  recommendation: Recommendation
  heatmap: Heatmap
  warnings: string[]
}

/** Asks the map to zoom to one checkpoint. A new object each time, so repeat clicks still fire. */
export interface FocusRequest {
  routeId: string
  mile: number
}

export interface AnalyzeRequest {
  origin: string
  destination: string
  departure_time: string
  load_weight_lb: number
  checkpoint_interval_mi: Interval
}