"""Copilot brief generation.

Turns structured mission state into plain-language briefs via the LLM client.
Falls back to a deterministic, data-backed summary when the LLM is unavailable
so the demo never hard-fails on network/key issues.
"""
from app.models.schemas import BriefRequest, BriefResponse
from app.services import risk_service
from app.services.dose_engine import estimate_daily_dose
from app.services.llm_client import get_llm_client

SYSTEM_PROMPT = (
    "You are Radiation Copilot, an AI mission-support officer for human spaceflight. "
    "You translate radiation telemetry and exposure limits into concise, actionable, "
    "plain-language guidance for mission planners and astronauts. Be specific, cite the "
    "numbers you are given, and always end with clear recommended actions. "
    "Never invent data that was not provided."
)

DAILY_TEMPLATE = """Mission: {mission_name} ({orbit_type}), {duration_days} days.
Latest telemetry:
- Planetary Kp index: {kp}
- Solar wind: Bt {bt} nT, Bz(GSM) {bz} nT, speed {speed} km/s
- SPE proton flux (>10 MeV): {flux} pfu (tripwire 10 pfu)
- Latest X-ray flare: {flare}

Dose assessment (simplified model, calibrated to ISS SPE measurements):
- Daily dose: {daily} mSv/day (GCR {gcr}, SPE {spe})
- Projected mission total: {total} mSv

Crew: {crew}

Write today's radiation status brief (max 200 words). Include the exposure trend,
any event concerns, and 3 recommended actions."""

ALERT_TEMPLATE = """Mission: {mission_name} ({orbit_type}).
ALERT — solar particle event detected:
- SPE proton flux (>10 MeV): {flux} pfu (tripwire 10 pfu)
- Kp index: {kp}

Crew exposure risk: {risk_level} ({utilization_30d} of 30-day limit used).
Crew: {crew}

Write an urgent radiation alert (max 150 words): what is happening, who is affected,
and the top mitigation actions (sheltering, EVA hold, equipment check)."""


def _fmt(x, suffix="", default="n/a"):
    return f"{x}{suffix}" if x is not None else default


def _render(req: BriefRequest) -> str:
    tele = req.telemetry or _empty_telemetry()
    dose = estimate_daily_dose(req.mission, tele)
    crew_line = ", ".join(f"{m.name} ({m.age}, {m.sex})" for m in req.crew) or "not specified"
    common = dict(
        mission_name=req.mission.name,
        orbit_type=req.mission.orbit_type,
        duration_days=req.mission.duration_days,
        kp=_fmt(tele.kp_index),
        bt=_fmt(tele.solar_wind_bt),
        bz=_fmt(tele.solar_wind_bz_gsm),
        speed=_fmt(tele.solar_wind_speed_km_s),
        flux=_fmt(tele.spe_proton_flux),
        flare=_fmt(tele.xray_flare_class),
        daily=dose.total_daily_msv,
        gcr=dose.gcr_daily_msv,
        spe=dose.spe_daily_msv,
        total=dose.projected_total_msv,
        crew=crew_line,
    )
    if req.kind == "alert":
        reports = risk_service.assess(req.mission, req.crew, tele)
        worst = max(reports, key=lambda r: r.utilization_30d) if reports else None
        common["risk_level"] = worst.level if worst else "n/a"
        common["utilization_30d"] = f"{worst.utilization_30d * 100:.0f}%" if worst else "n/a"
        return ALERT_TEMPLATE.format(**common)
    return DAILY_TEMPLATE.format(**common)


def _empty_telemetry():
    from app.models.schemas import TelemetrySnapshot
    return TelemetrySnapshot(sources_ok=False, degraded=True)


def generate_brief(req: BriefRequest) -> BriefResponse:
    prompt = _render(req)
    client = get_llm_client()
    if client is None:
        return BriefResponse(
            kind=req.kind,
            text=_fallback_brief(prompt),
            llm_used=False,
            provider="none",
        )
    try:
        text = asyncio_run(client.generate(SYSTEM_PROMPT, prompt))
        return BriefResponse(kind=req.kind, text=text, llm_used=True, provider=client.provider)
    except Exception:
        return BriefResponse(
            kind=req.kind,
            text=_fallback_brief(prompt),
            llm_used=False,
            provider=client.provider,
        )


def _fallback_brief(prompt: str) -> str:
    """Deterministic fallback: surface the structured context as a readable brief."""
    lines = [l for l in prompt.splitlines() if l.strip()]
    return (
        "⚠️ Copilot language model unavailable — showing data-backed summary.\n\n"
        + "\n".join(lines)
        + "\n\n(Configure GEMINI_API_KEY or switch LLM_PROVIDER to enable the AI brief.)"
    )


def asyncio_run(coro):
    """Run a coroutine from a sync context (FastAPI sync endpoint)."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Called from inside a running loop: run in a new event loop thread.
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()
