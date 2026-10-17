import { downloadReport } from '../lib/download'
import type { AnalyzeResponse } from '../types'

interface Props {
  result: AnalyzeResponse
  simulated: boolean
}

export default function ReportButton({ result, simulated }: Props) {
  return (
    <button
      type="button"
      className="report-button"
      onClick={() => downloadReport(result)}
      title={simulated ? 'The file is labelled SIMULATED STORM, not a live forecast.' : undefined}
    >
      {simulated ? 'Download simulated report (CSV)' : 'Download trip report (CSV)'}
    </button>
  )
}
