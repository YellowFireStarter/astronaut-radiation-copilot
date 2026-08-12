import { useCallback, useEffect, useState } from 'react'

const ORBITS = {
  leo_iss: 'LEO — ISS orbit (~400 km, 51.6°)',
  leo_polar: 'LEO — polar (~800 km)',
  lunar_transit: 'Lunar transit',
  deep_space: 'Deep space (Mars-class)',
}

const fmt = (v, suffix = '', d = 'n/a') => (v === null || v === undefined ? d : `${Number(v).toLocaleString()}${suffix}`)

function Card({ title, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function TelemetryRow({ label, value, ok = true }) {
  return (
    <div className="telemetry-row">
      <span className="telemetry-label">{label}</span>
      <span className={`telemetry-value ${ok ? '' : 'dim'}`}>{value}</span>
    </div>
  )
}

export default function App() {
  const [backend, setBackend] = useState('loading') // loading | online | offline
  const [telemetry, setTelemetry] = useState(null)
  const [limits, setLimits] = useState(null)
  const [mission, setMission] = useState({
    name: 'Artemis-style lunar mission',
    orbit_type: 'lunar_transit',
    duration_days: 30,
  })
  const [crew, setCrew] = useState([{ name: 'CDR', age: 40, sex: 'male' }, { name: 'PLT', age: 38, sex: 'female' }])
  const [forecast, setForecast] = useState(null)
  const [brief, setBrief] = useState(null)
  const [briefKind, setBriefKind] = useState('daily')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadTelemetry = useCallback(async () => {
    try {
      const [h, t, l] = await Promise.all([
        fetch('/health').then((r) => r.json()),
        fetch('/api/telemetry/latest').then((r) => r.json()),
        fetch('/api/limits').then((r) => r.json()),
      ])
      setBackend(h.status === 'ok' ? 'online' : 'offline')
      setTelemetry(t)
      setLimits(l)
    } catch {
      setBackend('offline')
    }
  }, [])

  useEffect(() => {
    loadTelemetry()
    const id = setInterval(loadTelemetry, 60000)
    return () => clearInterval(id)
  }, [loadTelemetry])

  const runForecast = async () => {
    setBusy(true)
    setError('')
    try {
      const resp = await fetch('/api/dose/forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mission),
      })
      if (!resp.ok) throw new Error(`Dose forecast failed (${resp.status})`)
      setForecast(await resp.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const runBrief = async (kind) => {
    setBusy(true)
    setError('')
    try {
      const resp = await fetch('/api/brief/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mission, crew, kind }),
      })
      if (!resp.ok) throw new Error(`Brief failed (${resp.status})`)
      setBrief(await resp.json())
      setBriefKind(kind)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>🛰️ Radiation Copilot</h1>
        <span className={`status-pill ${backend}`}>
          {backend === 'loading' ? 'Connecting…' : backend === 'online' ? 'Backend online' : 'Backend offline'}
        </span>
      </header>

      {backend === 'offline' && (
        <div className="banner warn">
          Backend unreachable — start it with <code>uvicorn app.main:app --reload --port 8000</code> in <code>backend/</code>.
        </div>
      )}

      <main className="grid">
        <Card title="Live telemetry (NOAA SWPC)" className="span-2">
          <TelemetryRow label="Planetary Kp index" value={fmt(telemetry?.kp_index, '', '—')} />
          <TelemetryRow label="SPE proton flux (&gt;10 MeV)" value={fmt(telemetry?.spe_proton_flux, ' pfu')} ok={!!telemetry?.spe_proton_flux} />
          <TelemetryRow label="Solar wind Bt" value={fmt(telemetry?.solar_wind_bt, ' nT')} />
          <TelemetryRow label="Solar wind Bz (GSM)" value={fmt(telemetry?.solar_wind_bz_gsm, ' nT')} />
          <TelemetryRow label="Solar wind speed" value={fmt(telemetry?.solar_wind_speed_km_s, ' km/s')} />
          <TelemetryRow label="Latest X-ray flare" value={telemetry?.xray_flare_class || '—'} />
          {telemetry?.degraded && <p className="note">Some data sources unreachable — showing partial data.</p>}
        </Card>

        <Card title="Mission configuration">
          <label>
            Mission name
            <input value={mission.name} onChange={(e) => setMission({ ...mission, name: e.target.value })} />
          </label>
          <label>
            Orbit
            <select value={mission.orbit_type} onChange={(e) => setMission({ ...mission, orbit_type: e.target.value })}>
              {Object.entries(ORBITS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Duration (days)
            <input
              type="number"
              min="1"
              max="730"
              value={mission.duration_days}
              onChange={(e) => setMission({ ...mission, duration_days: Number(e.target.value) })}
            />
          </label>
          <button onClick={runForecast} disabled={busy}>
            {busy ? 'Computing…' : 'Forecast dose'}
          </button>
          {forecast && (
            <div className="forecast">
              <p><strong>{forecast.mission.name}</strong> · {forecast.mission.duration_days} days</p>
              <p>Daily: <strong>{forecast.breakdown.total_daily_msv} mSv</strong> (GCR {forecast.breakdown.gcr_daily_msv} + SPE {forecast.breakdown.spe_daily_msv})</p>
              <p>Projected total: <strong>{forecast.breakdown.projected_total_msv} mSv</strong></p>
              {forecast.notes.map((n, i) => <p key={i} className="note">{n}</p>)}
            </div>
          )}
        </Card>

        <Card title="Crew exposure limits" className="span-2">
          {limits ? (
            <table>
              <thead>
                <tr><th>Window</th><th>Limit</th><th>Note</th></tr>
              </thead>
              <tbody>
                <tr><td>30-day</td><td>{limits['30_day_msv']} mSv</td><td rowSpan="3">{limits.note}</td></tr>
                <tr><td>Annual</td><td>{limits.annual_msv} mSv</td></tr>
                <tr><td>Career</td><td>{limits.career_msv} mSv</td></tr>
              </tbody>
            </table>
          ) : (
            <p className="note">Limits unavailable.</p>
          )}
        </Card>

        <Card title="Copilot brief" className="span-2">
          <div className="btn-row">
            <button onClick={() => runBrief('daily')} disabled={busy}>Daily brief</button>
            <button onClick={() => runBrief('alert')} disabled={busy} className="secondary">SPE alert</button>
          </div>
          {brief ? (
            <div className="brief">
              <p className="note">
                {brief.llm_used ? `Generated by ${brief.provider} (${brief.kind})` : 'LLM unavailable — data-backed summary'}
              </p>
              <pre>{brief.text}</pre>
            </div>
          ) : (
            <p className="note">Generate a brief to see the copilot output.</p>
          )}
        </Card>
      </main>

      {error && <div className="banner error">{error}</div>}
      <footer className="footer">
        AI Builders Challenge with IBM Bob · August 2026 · placeholder dose constants pending verification
      </footer>
    </div>
  )
}
