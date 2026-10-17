import { LIVE_SOURCE_NOTE } from '../lib/weatherSource'
import type { AnalyzeResponse } from '../types'

interface Props {
  result: AnalyzeResponse
}

/** Says where the weather in the results came from. Simulated data is never shown without it. */
export default function WeatherSourceBanner({ result }: Props) {
  if (result.weather_source !== 'demo' || !result.demo) {
    return <p className="source-note">{LIVE_SOURCE_NOTE}</p>
  }
  return (
    <section className="banner demo" aria-label="Simulated weather">
      <p className="demo-title">{result.demo.label}</p>
      <p>{result.demo.description}</p>
      <ul>
        {result.demo.how_to_read.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  )
}
