"""MCP server exposing the Astronaut Radiation Copilot API as tools.

Lets AI agents (IBM Bob, OpenClaw, Claude Desktop, ...) drive the copilot
through standard MCP tools instead of raw REST calls:

    get_live_telemetry   - latest NOAA SWPC snapshot (Kp, solar wind, flux)
    get_spe_alert        - current solar particle event alert level
    get_proton_flux      - GOES >=10 MeV proton flux history (pfu)
    get_kp_history       - planetary Kp activity history
    forecast_dose        - projected dose for a mission profile
    assess_risk          - per-crew exposure vs NASA/NCRP limits
    plan_mission         - what-if planner: verdict, margins, max duration
    generate_brief       - copilot narrative brief (Gemini-backed)

Run over stdio (default):  python mcp_server.py
The backend REST API must be reachable at $COPILOT_BACKEND_URL (default
http://localhost:8000). Built with the official `mcp` Python SDK.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

def _load_dotenv() -> None:
    """Load mcp/.env into the environment (does not override existing vars)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    if key and key not in os.environ:
                        os.environ[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass


_load_dotenv()

BACKEND_URL = os.environ.get("COPILOT_BACKEND_URL", "http://localhost:8000").rstrip("/")

# Backend route paths (must match the backend's ROUTE_* settings).
ROUTES = {
    "telemetry_latest": os.environ.get("COPILOT_ROUTE_TELEMETRY_LATEST", "/api/telemetry/latest"),
    "spe_alert": os.environ.get("COPILOT_ROUTE_SPE_ALERT", "/api/spe/alert"),
    "flux": os.environ.get("COPILOT_ROUTE_FLUX", "/api/telemetry/flux"),
    "kp": os.environ.get("COPILOT_ROUTE_KP", "/api/telemetry/kp"),
    "dose_forecast": os.environ.get("COPILOT_ROUTE_DOSE_FORECAST", "/api/dose/forecast"),
    "risk_assess": os.environ.get("COPILOT_ROUTE_RISK_ASSESS", "/api/risk/assess"),
    "plan": os.environ.get("COPILOT_ROUTE_PLAN", "/api/plan"),
    "brief_generate": os.environ.get("COPILOT_ROUTE_BRIEF_GENERATE", "/api/brief/generate"),
}

mcp = FastMCP("radiation-copilot")


async def _api(method: str, path: str, payload: dict | None = None, params: dict | None = None) -> Any:
    url = f"{BACKEND_URL}{path}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.request(method, url, json=payload, params=params)
        resp.raise_for_status()
        return resp.json()


def _crew(crew_json: str) -> list[dict]:
    crew = json.loads(crew_json or "[]")
    if not isinstance(crew, list) or not crew:
        raise ValueError("crew_json must be a non-empty JSON array, e.g. "
                         '[{"name":"CDR","age":40,"sex":"male"}]')
    for c in crew:
        if not all(k in c for k in ("name", "age", "sex")):
            raise ValueError('each crew member needs "name", "age", "sex"')
    return crew


def _mission(orbit_type: str, duration_days: int, mission_name: str = "MCP mission") -> dict:
    return {"name": mission_name, "orbit_type": orbit_type, "duration_days": int(duration_days)}


@mcp.tool()
async def get_live_telemetry() -> str:
    """Latest live space-weather telemetry from NOAA SWPC (Kp, solar wind, proton flux)."""
    data = await _api("GET", ROUTES["telemetry_latest"])
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
async def get_spe_alert() -> str:
    """Current solar particle event (SPE) alert: level, NOAA S-scale, flux, recommended action."""
    data = await _api("GET", ROUTES["spe_alert"])
    return (f"SPE alert: {data['level'].upper()} (S-scale {data['s_scale']})\n"
            f"Proton flux (>=10 MeV): {data['flux_pfu']} pfu (tripwire {data['tripwire_pfu']})\n"
            f"Latest X-ray flare: {data.get('flare_class') or 'none'}\n"
            f"Action: {data['action']}")


@mcp.tool()
async def get_proton_flux(hours: int = 6) -> str:
    """GOES proton flux history (>=10 MeV proxy, pfu). `hours` in 1..6."""
    hours = max(1, min(int(hours), 6))
    data = await _api("GET", ROUTES["flux"], params={"hours": hours})
    pts = data.get("points", [])
    if not pts:
        return "No proton flux data available."
    return (f"Proton flux (last {hours}h, {len(pts)} samples):\n"
            + "\n".join(f"  {p['time_tag']}  {p['flux_pfu']} pfu" for p in pts[-12:])
            + f"\nTripwire: {data['tripwire_pfu']} pfu | S-scale bands: "
            + ", ".join(f"{b['label']} >= {b['pfu']}" for b in data.get("s_scale_bands", [])))


@mcp.tool()
async def get_kp_history(points: int = 288) -> str:
    """Recent planetary Kp index history (geomagnetic activity)."""
    points = max(24, min(int(points), 288))
    data = await _api("GET", ROUTES["kp"], params={"points": points})
    pts = data.get("points", [])
    if not pts:
        return "No Kp data available."
    latest = pts[-1]
    return (f"Kp history: {len(pts)} samples; latest Kp = {latest['kp_index']} "
            f"at {latest['time_tag']}. Last 12: "
            + ", ".join(str(p["kp_index"]) for p in pts[-12:]))


@mcp.tool()
async def forecast_dose(orbit_type: str, duration_days: int, mission_name: str = "MCP mission") -> str:
    """Project radiation dose for a mission. orbit_type: leo_iss|leo_polar|lunar_transit|deep_space|planetary_surface."""
    data = await _api("POST", ROUTES["dose_forecast"],
                      payload=_mission(orbit_type, duration_days, mission_name))
    b = data["breakdown"]
    lines = [
        f"Mission: {data['mission']['name']} ({orbit_type}, {duration_days}d)",
        f"Daily dose: {b['total_daily_msv']} mSv (GCR {b['gcr_daily_msv']} + SPE {b['spe_daily_msv']})",
        f"Projected total: {b['projected_total_msv']} mSv",
    ]
    lines += [f"Note: {n}" for n in data.get("notes", [])]
    return "\n".join(lines)


@mcp.tool()
async def assess_risk(orbit_type: str, duration_days: int, crew_json: str) -> str:
    """Per-crew exposure vs NASA/NCRP limits. crew_json: [{"name","age","sex"}...]."""
    crew = _crew(crew_json)
    data = await _api("POST", ROUTES["risk_assess"],
                      payload={"mission": _mission(orbit_type, duration_days), "crew": crew})
    lines = [f"Risk assessment - {data['mission']['orbit_type']} x {data['mission']['duration_days']}d:"]
    for r in data["reports"]:
        lines.append(
            f"  {r['crew']['name']} ({r['crew']['age']} {r['crew']['sex']}): "
            f"{r['cumulative_msv']} mSv projected | level {r['level'].upper()} | "
            f"career util {r['utilization_career']*100:.1f}% of {r['limit_career_msv']} mSv"
        )
        lines.append(f"    -> {r['recommendation']}")
    return "\n".join(lines)


@mcp.tool()
async def plan_mission(orbit_type: str, duration_days: int, crew_json: str) -> str:
    """What-if mission planner: feasibility verdict, utilization, max duration, SPE overlay."""
    crew = _crew(crew_json)
    data = await _api("POST", ROUTES["plan"],
                      payload={"mission": _mission(orbit_type, duration_days), "crew": crew})
    lines = [
        f"Verdict: {data['verdict'].upper()} | projected {data['projected_total_msv']} mSv "
        f"| worst utilization {data['worst_utilization']*100:.1f}% "
        f"| max duration to 80% career budget: {data['max_duration_days']} days",
        f"SPE overlay: {data['spe_alert']['level']} ({data['spe_alert']['s_scale']})",
    ]
    for r in data["crew_reports"]:
        lines.append(
            f"  {r['name']}: {r['projected_msv']} mSv / {r['career_limit_msv']} mSv career "
            f"({r['utilization_career']*100:.1f}%)"
        )
    lines += [f"Note: {n}" for n in data.get("notes", [])]
    return "\n".join(lines)


@mcp.tool()
async def generate_brief(kind: str = "daily", orbit_type: str = "lunar_transit",
                         duration_days: int = 30, crew_json: str = "[]") -> str:
    """Copilot narrative brief. kind: daily|alert. Gemini-backed when the key is configured."""
    crew = json.loads(crew_json or "[]")
    payload = {
        "mission": _mission(orbit_type, duration_days),
        "crew": crew,
        "kind": kind,
    }
    data = await _api("POST", ROUTES["brief_generate"], payload=payload)
    return (f"[{data['kind'].upper()} brief - {'LLM: ' + data['provider'] if data['llm_used'] else 'data-backed fallback'}]\n"
            + data["text"])


if __name__ == "__main__":
    mcp.run()
