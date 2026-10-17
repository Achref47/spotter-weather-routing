// Turns a failed server response into a sentence for the user. Pure, so `npm test` covers it.

/** Field errors from a 400 response, e.g. { load_weight_lb: ["..."] } to "load weight lb: ...". */
export function describeValidation(details: unknown): string {
  if (details && typeof details === 'object') {
    return Object.entries(details as Record<string, unknown>)
      .map(([field, msgs]) => {
        const text = Array.isArray(msgs) ? msgs.join(' ') : String(msgs)
        return `${field.replace(/_/g, ' ')}: ${text}`
      })
      .join(' • ')
  }
  return 'Please check your input.'
}

/** The message for a non-2xx response. `body` is the parsed JSON, or null if it was not JSON. */
export function messageForResponse(status: number, body: unknown): string {
  const info = body && typeof body === 'object' ? (body as { error?: unknown; details?: unknown }) : null
  if (status === 400) return describeValidation(info?.details)
  if (status === 429) return 'Too many requests. Please wait a minute and try again.'
  if (status === 502 || status === 503 || status === 504) {
    return 'The server is waking up or temporarily unavailable. Wait a minute and try again.'
  }
  if (typeof info?.error === 'string' && info.error.trim() !== '') return info.error
  return `The server returned an error (${status}).`
}
