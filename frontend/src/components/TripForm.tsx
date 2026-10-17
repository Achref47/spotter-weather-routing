import { useState } from 'react'
import type { FormEvent } from 'react'
import { defaultDeparture } from '../lib/format'
import type { AnalyzeRequest, Interval } from '../types'

interface Props {
  onSubmit: (request: AnalyzeRequest) => void
  loading: boolean
}

export default function TripForm({ onSubmit, loading }: Props) {
  const [origin, setOrigin] = useState('Houston, TX')
  const [destination, setDestination] = useState('Atlanta, GA')
  const [departure, setDeparture] = useState(defaultDeparture)
  const [loadLb, setLoadLb] = useState('42000')
  const [interval, setIntervalMi] = useState<Interval>(25)
  const [formError, setFormError] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const when = new Date(departure)
    const load = Number(loadLb)

    if (origin.trim().length < 2 || destination.trim().length < 2) {
      setFormError('Enter an origin and a destination.')
      return
    }
    if (Number.isNaN(when.getTime())) {
      setFormError('Choose a departure date and time.')
      return
    }
    if (!Number.isFinite(load) || load < 0 || load > 80000) {
      setFormError('Load weight must be between 0 and 80,000 lb.')
      return
    }

    setFormError(null)
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      departure_time: when.toISOString().replace(/\.\d{3}Z$/, 'Z'),
      load_weight_lb: load,
      checkpoint_interval_mi: interval,
    })
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit} noValidate>
      <label>
        Origin
        <input value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="City, State" />
      </label>
      <label>
        Destination
        <input
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="City, State"
        />
      </label>
      <label>
        Departure (your local time)
        <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} />
      </label>
      <div className="row">
        <label>
          Load weight (lb)
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={80000}
            step={100}
            value={loadLb}
            onChange={(e) => setLoadLb(e.target.value)}
          />
        </label>
        <label>
          Weather checkpoints
          <select value={interval} onChange={(e) => setIntervalMi(Number(e.target.value) as Interval)}>
            <option value={10}>Every 10 mi</option>
            <option value={25}>Every 25 mi</option>
            <option value={50}>Every 50 mi</option>
          </select>
        </label>
      </div>
      {formError && (
        <p className="form-error" role="alert">
          {formError}
        </p>
      )}
      <button type="submit" disabled={loading}>
        {loading ? 'Analyzing…' : 'Compare routes'}
      </button>
    </form>
  )
}