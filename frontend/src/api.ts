import { messageForResponse } from './lib/apiErrors'
import type { AnalyzeRequest, AnalyzeResponse } from './types'

const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {}

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

  if (!resp.ok) throw new ApiError(messageForResponse(resp.status, data))
  return data as AnalyzeResponse
}