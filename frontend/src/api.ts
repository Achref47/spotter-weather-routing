import type { AnalyzeRequest, AnalyzeResponse } from './types'

const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {}

function describeValidation(details: unknown): string {
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

export async function analyzeTrip(
  body: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  let resp: Response
  try {
    resp = await fetch(`${API}/api/trips/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError('Cannot reach the server. If it was idle, wait a minute and try again.')
  }

  let data: unknown = null
  try {
    data = await resp.json()
  } catch {
    // the body was not JSON; fall through to the generic message below
  }

  if (!resp.ok) {
    const info = data as { error?: string; details?: unknown } | null
    if (resp.status === 400) throw new ApiError(describeValidation(info?.details))
    throw new ApiError(info?.error ?? `The server returned an error (${resp.status}).`)
  }
  return data as AnalyzeResponse
}