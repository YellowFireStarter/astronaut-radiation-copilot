import { useCallback, useEffect, useState } from 'react'

const ORBITS = {
  leo_iss: 'LEO – ISS orbit (~400 km, 51.6°)',
  leo_polar: 'LEO – polar (~800 km)',
  lunar_transit: 'Lunar transit',
  deep_space: 'Deep space (Mars-class)',
  planetary_surface: 'Planetary surface (Moon/Mars)',
}

const fmt = (v, suffix = '', d = 'n/a') => (v === null || v === undefined ? d : `${Number(v).toLocaleString()}${suffix}`)

const ALERT_COLORS = {
  nominal: { color: 'var(--ok)', label: 'NOMINAL' },
  watch: { color: 'var(--warn)', label: 'WATCH' },
  warning: { color: '#fb923c', label: 'WARNING' },
  emergency: { color: 'var(--err)', label: 'EMERGENCY' },
}

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

function SpeBanner({ alert }) {
  if (!alert) return null
  const meta = ALERT_COLORS[alert.level] || ALERT_COLORS.nominal
  return (
    <div className="spe-banner" style={{ borderColor: meta.color, color: meta.color }}>
      <span className="spe-level" style={{ background: meta.color }}>{meta.label}</span>
      <span>
        SPE alert · S-scale <strong>{alert.s_scale}</strong> · flux{' '}
        <strong>{alert.flux_pfu == null ? 'n/a' : `${alert.flux_pfu} pfu`}</strong>
        {alert.flare_class ? ` · flare ${alert.flare_class}` : ''}
      </span>
      {alert.forecast && (
        <span className="spe-forecast" title={`SEP onset ${Math.round(alert.forecast.probability * 100)}% within ${alert.forecast.window_h}h (heuristic)`}>
          SEP risk {alert.forecast.risk_label} · {Math.round(alert.forecast.probability * 100)}% / {alert.forecast.window_h}h
        </span>
      )}
      <span className="spe-action">{alert.action}</span>
    </div>
  )
}

function FluxChart({ points, tripwire }) {
  const W = 560
  const H = 180
  const PAD_L = 46
  const PAD_R = 12
  const PAD_T = 14
  const PAD_B = 26
  const MIN = 1e-4
  const MAX = 1e3

  const y = (v) => {
    const val = Math.max(v, MIN)
    return PAD_T + (1 - (Math.log10(val) - Math.log10(MIN)) / (Math.log10(MAX) - Math.log10(MIN))) * (H - PAD_T - PAD_B)
  }
  const x = (i) => (points.length <= 1 ? PAD_L : PAD_L + (i / (points.length - 1)) * (W - PAD_L - PAD_R))

  const gridLines = [1e-2, 1, 10, 100, 1000]
  const polyline = points.map((p, i) => `${x(i).toFixed(1)},${y(p.flux_pfu).toFixed(1)}`).join(' ')
  const tripY = y(tripwire)
  const last = points[points.length - 1]

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Proton flux history">
        {gridLines.map((g) => (
          <g key={g}>
            <line x1={PAD_L} x2={W - PAD_R} y1={y(g)} y2={y(g)} className="gridline" />
            <text x={PAD_L - 6} y={y(g) + 3} className="axis-label" textAnchor="end">
              {g >= 1 ? g : g.toExponential(0)}
            </text>
          </g>
        ))}
        <rect x={PAD_L} y={y(1000)} width={W - PAD_L - PAD_R} height={y(100) - y(1000)} className="band band-severe" />
        <rect x={PAD_L} y={y(100)} width={W - PAD_L - PAD_R} height={y(10) - y(100)} className="band band-warn" />
        <line x1={PAD_L} x2={W - PAD_R} y1={tripY} y2={tripY} className="tripwire" />
        <text x={W - PAD_R - 2} y={tripY - 4} className="tripwire-label" textAnchor="end">
          SPE tripwire {tripwire} pfu
        </text>
        {points.length > 1 && <polyline points={polyline} className="flux-line" />}
        {last && <circle cx={x(points.length - 1)} cy={y(last.flux_pfu)} r="3.5" className="flux-dot" />}
        <text x={PAD_L} y={H - 8} className="axis-label">
          {points[0]?.time_tag?.slice(11, 16) || ''} UTC
        </text>
        <text x={W - PAD_R} y={H - 8} className="axis-label" textAnchor="end">
          {last?.time_tag?.slice(11, 16) || ''} UTC
        </text>
      </svg>
      <p className="note">
        ≥10 MeV proton flux (pfu, log scale) · shaded bands: S1 watch ≥10 · S2 warning ≥100 · S3+ ≥1000
      </p>
    </div>
  )
}

function KpStrip({ points }) {
  if (!points || points.length === 0) return <p className="note">Kp history unavailable.</p>
  const bar = (kp) => (kp >= 5 ? 'var(--err)' : kp >= 4 ? 'var(--warn)' : kp >= 3 ? '#93c5fd' : 'var(--ok)')
  // Downsample to ~96 bars so the strip always fits its card
  const step = Math.max(1, Math.ceil(points.length / 96))
  const bars = points.filter((_, i) => i % step === 0)
  return (
    <div className="kp-strip" title="Planetary Kp index (recent)">
      {bars.map((p, i) => (
        <div key={i} className="kp-bar" style={{ background: bar(p.kp_index) }} />
      ))}
      <div className="kp-legend">
        <span className="note">Kp 0–2</span>
        <span className="note">3</span>
        <span className="note">4</span>
        <span className="note">5+ storm</span>
      </div>
    </div>
  )
}

function UtilBar({ pct, limit }) {
  const p = Math.min(pct * 100, 100)
  const color = pct >= 0.8 ? 'var(--err)' : pct >= 0.5 ? 'var(--warn)' : 'var(--ok)'
  return (
    <div className="util">
      <div className="util-track">
        <div className="util-fill" style={{ width: `${p}%`, background: color }} />
      </div>
      <span className="util-label">{p.toFixed(0)}% of {limit} mSv</span>
    </div>
  )
}

function VerdictBadge({ verdict }) {
  const map = {
    feasible: { label: 'FEASIBLE', color: 'var(--ok)' },
    caution: { label: 'CAUTION', color: 'var(--warn)' },
    infeasible: { label: 'INFEASIBLE', color: 'var(--err)' },
  }
  const m = map[verdict] || map.caution
  return <span className="verdict" style={{ borderColor: m.color, color: m.color }}>{m.label}</span>
}

export default function App() {
  const [backend, setBackend] = useState('loading')
  const [telemetry, setTelemetry] = useState(null)
  const [limits, setLimits] = useState(null)
  const [alert, setAlert] = useState(null)
  const [flux, setFlux] = useState(null)
  const [kp, setKp] = useState(null)
  const [mission, setMission] = useState({
    name: 'Artemis-style lunar mission',
    orbit_type: 'lunar_transit',
    duration_days: 30,
  })
  const [crew, setCrew] = useState([
    { name: 'CDR', age: 40, sex: 'male' },
    { name: 'PLT', age: 38, sex: 'female' },
  ])
  const [forecast, setForecast] = useState(null)
  const [plan, setPlan] = useState(null)
  const [brief, setBrief] = useState(null)
  const [briefKind, setBriefKind] = useState('daily')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const loadTelemetry = useCallback(async () => {
    try {
      const [h, t, l, a, f, k] = await Promise.all([
        fetch('/health').then((r) => r.json()),
        fetch('/api/telemetry/latest').then((r) => r.json()),
        fetch('/api/limits').then((r) => r.json()),
        fetch('/api/spe/alert').then((r) => r.json()),
        fetch('/api/telemetry/flux?hours=6').then((r) => r.json()),
        fetch('/api/telemetry/kp?points=288').then((r) => r.json()),
      ])
      setBackend(h.status === 'ok' ? 'online' : 'offline')
      setTelemetry(t)
      setLimits(l)
      setAlert(a)
      setFlux(f)
      setKp(k)
    } catch {
      setBackend('offline')
    }
  }, [])

  useEffect(() => {
    loadTelemetry()
    const id = setInterval(loadTelemetry, 60000)
    return () => clearInterval(id)
  }, [loadTelemetry])

  const setCrewRow = (i, patch) => setCrew(crew.map((c, j) => (j === i ? { ...c, ...patch } : c)))

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

  const runPlan = async () => {
    setBusy(true)
    setError('')
    try {
      const resp = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mission, crew }),
      })
      if (!resp.ok) throw new Error(`Plan failed (${resp.status})`)
      setPlan(await resp.json())
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
        <h1>⚡ Astronaut Radiation Copilot</h1>
        <span className={`status-pill ${backend}`}>
          {backend === 'loading' ? 'Connecting…' : backend === 'online' ? 'Backend online' : 'Backend offline'}
        </span>
      </header>

      {backend === 'offline' && (
        <div className="banner warn">
          Backend unreachable – start it with <code>uvicorn app.main:app --reload --port 8000</code> in <code>backend/</code>.
        </div>
      )}

      {backend === 'online' && <SpeBanner alert={alert} />}

      <main className="grid">
        <Card title="SPE proton flux (NOAA GOES)" className="span-2">
          <FluxChart points={flux?.points || []} tripwire={flux?.tripwire_pfu || 10} />
        </Card>

        <Card title="Live telemetry (NOAA SWPC)">
          <TelemetryRow label="Planetary Kp index" value={fmt(telemetry?.kp_index, '', '—')} />
          <TelemetryRow label="SPE proton flux (>10 MeV)" value={fmt(telemetry?.spe_proton_flux, ' pfu')} ok={!!telemetry?.spe_proton_flux} />
          <TelemetryRow label="Solar wind Bt" value={fmt(telemetry?.solar_wind_bt, ' nT')} />
          <TelemetryRow label="Solar wind Bz (GSM)" value={fmt(telemetry?.solar_wind_bz_gsm, ' nT')} />
          <TelemetryRow label="Solar wind speed" value={fmt(telemetry?.solar_wind_speed_km_s, ' km/s')} />
          <TelemetryRow label="Latest X-ray flare" value={telemetry?.xray_flare_class || '—'} />
          {telemetry?.degraded && <p className="note">Some data sources unreachable – showing partial data.</p>}
        </Card>

        <Card title="Kp activity strip">
          <KpStrip points={kp?.points || []} />
        </Card>

        <Card title="Mission configuration" className="span-2">
          <div className="form-grid">
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
          </div>

          <div className="crew-editor">
            <h3>Crew</h3>
            {crew.map((c, i) => (
              <div className="crew-row" key={i}>
                <input value={c.name} placeholder="Name" onChange={(e) => setCrewRow(i, { name: e.target.value })} />
                <input
                  type="number" min="18" max="75" value={c.age}
                  onChange={(e) => setCrewRow(i, { age: Number(e.target.value) })}
                />
                <select value={c.sex} onChange={(e) => setCrewRow(i, { sex: e.target.value })}>
                  <option value="male">male</option>
                  <option value="female">female</option>
                </select>
                <button className="icon-btn" onClick={() => setCrew(crew.filter((_, j) => j !== i))} disabled={crew.length <= 1}>✕</button>
              </div>
            ))}
            <button className="secondary" onClick={() => setCrew([...crew, { name: `CREW${crew.length + 1}`, age: 35, sex: 'male' }])}>
              + Add crew
            </button>
          </div>

          <div className="btn-row">
            <button onClick={runForecast} disabled={busy}>{busy ? 'Computing…' : 'Forecast dose'}</button>
            <button onClick={runPlan} disabled={busy} className="secondary">What-if plan</button>
          </div>

          {forecast && (
            <div className="forecast">
              <p><strong>{forecast.mission.name}</strong> · {forecast.mission.duration_days} days · {forecast.mission.orbit_type}</p>
              <p>Daily: <strong>{forecast.breakdown.total_daily_msv} mSv</strong> (GCR {forecast.breakdown.gcr_daily_msv} + SPE {forecast.breakdown.spe_daily_msv})</p>
              <p>Projected total: <strong>{forecast.breakdown.projected_total_msv} mSv</strong></p>
              {forecast.notes.map((n, i) => <p key={i} className="note">{n}</p>)}
            </div>
          )}

          {plan && (
            <div className="plan">
              <div className="plan-head">
                <h3>What-if plan · {plan.mission.name}</h3>
                <VerdictBadge verdict={plan.verdict} />
              </div>
              <p>
                Projected total: <strong>{plan.projected_total_msv} mSv</strong> · max duration before 80% career budget:{' '}
                <strong>{plan.max_duration_days} days</strong> · SPE overlay: <strong>{plan.spe_alert.level}</strong>
              </p>
              <table>
                <thead>
                  <tr><th>Crew</th><th>Age/sex</th><th>Career limit</th><th>Projected</th><th>Utilization</th></tr>
                </thead>
                <tbody>
                  {plan.crew_reports.map((r, i) => (
                    <tr key={i}>
                      <td>{r.name}</td>
                      <td>{r.age} {r.sex}</td>
                      <td>{r.career_limit_msv} mSv</td>
                      <td>{r.projected_msv} mSv</td>
                      <td><UtilBar pct={r.utilization_career} limit={r.career_limit_msv} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {plan.notes.map((n, i) => <p key={i} className="note">{n}</p>)}
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
                {brief.llm_used ? `Generated by ${brief.provider} (${brief.kind})` : 'LLM unavailable – data-backed summary'}
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
        AI Builders Challenge with IBM Bob · August 2026 · dose constants pending verification (see dose_engine.py TODO)
      </footer>
    </div>
  )
}
