// Pure helpers for the checkpoint table. No imports, so they run under `npm test`.

/** "25", or "794.4" for the final checkpoint at the exact end of the route. */
export function formatMile(mile: number): string {
  return Number.isInteger(mile) ? String(mile) : mile.toFixed(1)
}

/** A weather reading, or an em dash when the forecast had no value (never shown as 0). */
export function formatReading(value: number | null, digits: number): string {
  return value === null ? '—' : value.toFixed(digits)
}

/** Compact arrival time for a table cell, e.g. "Sat 03:00 PM", in the viewer's time zone. */
export function etaShort(iso: string, locale?: string, timeZone?: string): string {
  return new Date(iso).toLocaleString(locale, {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  })
}

/** Identity of one checkpoint across routes, used to highlight the focused table row. */
export function checkpointKey(routeId: string, mile: number): string {
  return `${routeId}:${mile}`
}
