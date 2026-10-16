import { useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export default function App() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    fetch(`${API}/api/health`)
      .then((r) => r.json())
      .then((d) => setStatus(d.status))
      .catch(() => setStatus('backend unreachable'))
  }, [])

  return (
    <main>
      <h1>Weather-Aware Truck Routing</h1>
      <p>Backend status: {status}</p>
    </main>
  )
}