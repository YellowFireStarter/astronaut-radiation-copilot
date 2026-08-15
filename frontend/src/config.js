// Route configuration for the copilot dashboard.
// Defaults match the backend ROUTE_* settings in backend/.env.
// Override per environment via frontend/.env (VITE_ROUTE_*), e.g.:
//   VITE_ROUTE_SPE_ALERT=/api/spe/alert
const ROUTE = {
  health: import.meta.env.VITE_ROUTE_HEALTH || '/health',
  telemetryLatest: import.meta.env.VITE_ROUTE_TELEMETRY_LATEST || '/api/telemetry/latest',
  limits: import.meta.env.VITE_ROUTE_LIMITS || '/api/limits',
  speAlert: import.meta.env.VITE_ROUTE_SPE_ALERT || '/api/spe/alert',
  flux: import.meta.env.VITE_ROUTE_FLUX || '/api/telemetry/flux',
  kp: import.meta.env.VITE_ROUTE_KP || '/api/telemetry/kp',
  doseForecast: import.meta.env.VITE_ROUTE_DOSE_FORECAST || '/api/dose/forecast',
  plan: import.meta.env.VITE_ROUTE_PLAN || '/api/plan',
  briefGenerate: import.meta.env.VITE_ROUTE_BRIEF_GENERATE || '/api/brief/generate',
}

export default ROUTE
