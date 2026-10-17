const RISK_COLORS: Record<number, string> = {
  [-1]: '#8b949e', // unknown
  0: '#2ea043', // Low
  1: '#d4c13b', // Moderate
  2: '#f0883e', // High
  3: '#f85149', // Severe
  4: '#b062ff', // No Travel
}

export function riskColor(level: number | null | undefined): string {
  return RISK_COLORS[level ?? -1] ?? RISK_COLORS[-1]
}

/** Text colour that stays readable on a risk pill: dark on the light yellow and orange. */
export function riskTextColor(level: number | null | undefined): string {
  return level === 1 || level === 2 ? '#111111' : '#ffffff'
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function avgRiskLabel(avg: number | null): string {
  return avg === null ? 'n/a' : `${avg.toFixed(2)} / 4`
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** Value for <input type="datetime-local">, in the browser's local time. */
export function toLocalInputValue(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** One hour from now, on the hour. */
export function defaultDeparture(): string {
  const d = new Date(Date.now() + 3_600_000)
  d.setMinutes(0, 0, 0)
  return toLocalInputValue(d)
}


const ROUTE_COLORS = ['#1f6feb', '#0aa6a6', '#c2185b']

/** Line color for a route id such as "route-2". */
export function routeColor(routeId: string): string {
  const n = Number(routeId.replace('route-', ''))
  const index = Number.isFinite(n) ? Math.max(0, n - 1) : 0
  return ROUTE_COLORS[index % ROUTE_COLORS.length] ?? ROUTE_COLORS[0]
}