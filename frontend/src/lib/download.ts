import { buildReportCsv, reportFilename, withBom } from './csvReport.ts'
import type { AnalyzeResponse } from '../types'

/**
 * Builds the report from `result` at the moment of the click and saves it. DOM only; the content
 * and filename logic is in csvReport.ts, which is the part `npm test` covers.
 */
export function downloadReport(result: AnalyzeResponse, generatedAt: Date = new Date()): void {
  const csv = withBom(buildReportCsv(result, generatedAt))
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = reportFilename(result, generatedAt)
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Revoke after the browser has started the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
