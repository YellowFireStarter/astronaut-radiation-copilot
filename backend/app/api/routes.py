"""API routes."""
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import (
    BriefRequest,
    BriefResponse,
    CrewMember,
    DoseForecast,
    FluxSeries,
    KpSeries,
    MissionProfile,
    PlanResult,
    RiskAssessment,
    SepForecast,
    SpeAlert,
    TelemetrySnapshot,
)
from app.services import risk_service, spe_alert
from app.services.sep_forecast import forecast as forecast_sep
from app.services.brief_generator import generate_brief
from app.services.dose_engine import estimate_daily_dose, SPE_TRIPWIRE_PFU
from app.services.noaa_client import NOAAClient
from app.services.planner import plan as plan_mission

router = APIRouter()
noaa = NOAAClient()


@router.get("/health")
async def health():
    s = get_settings()
    snapshot = await noaa.latest_snapshot()
    return {
        "status": "ok",
        "app": s.app_name,
        "version": s.version,
        "llm_provider": s.llm_provider,
        "data_sources": {
            "noaa_swpc": "ok" if snapshot.sources_ok else "degraded",
        },
        "time": None,
    }


@router.get("/api/telemetry/latest", response_model=TelemetrySnapshot)
async def telemetry_latest():
    return await noaa.latest_snapshot()


@router.get("/api/limits")
async def limits():
    from app.services.risk_service import LIMIT_30D_MSV, LIMIT_ANNUAL_MSV, NASA_CAREER_LIMIT_MSV
    return {
        "30_day_msv": LIMIT_30D_MSV,
        "annual_msv": LIMIT_ANNUAL_MSV,
        "career_msv": NASA_CAREER_LIMIT_MSV,
        "note": "30-day/annual per NCRP 132 (BFO); career per NASA-STD-3001 (600 mSv). NCRP age/sex matrix used per-crew in risk assessment.",
    }


@router.post("/api/dose/forecast", response_model=DoseForecast)
async def dose_forecast(mission: MissionProfile):
    telemetry = await noaa.latest_snapshot()
    result = estimate_daily_dose(mission, telemetry)
    return DoseForecast(
        mission=mission,
        breakdown={
            "gcr_daily_msv": result.gcr_daily_msv,
            "spe_daily_msv": result.spe_daily_msv,
            "total_daily_msv": result.total_daily_msv,
            "projected_total_msv": result.projected_total_msv,
        },
        notes=result.notes,
    )


@router.post("/api/risk/assess", response_model=RiskAssessment)
async def risk_assess(mission: MissionProfile, crew: list[CrewMember]):
    if not crew:
        raise HTTPException(status_code=422, detail="Provide at least one crew member")
    telemetry = await noaa.latest_snapshot()
    reports = risk_service.assess(mission, crew, telemetry)
    return RiskAssessment(mission=mission, reports=reports)


@router.post("/api/brief/generate", response_model=BriefResponse)
async def brief_generate(req: BriefRequest):
    if req.telemetry is None:
        req.telemetry = await noaa.latest_snapshot()
    return generate_brief(req)


@router.get("/api/spe/forecast", response_model=SepForecast)
async def spe_forecast():
    """SEP onset forecast from the latest GOES flare class (heuristic)."""
    telemetry = await noaa.latest_snapshot()
    return SepForecast(**forecast_sep(telemetry.xray_flare_class))


@router.get("/api/spe/alert", response_model=SpeAlert)
async def spe_alert_now():
    """Current solar particle event alert level."""
    telemetry = await noaa.latest_snapshot()
    return SpeAlert(**spe_alert.evaluate(telemetry))


@router.get("/api/telemetry/flux", response_model=FluxSeries)
async def flux_history(hours: int = 6):
    """SPE-proxy proton flux history (>= 10 MeV channels)."""
    hours = max(1, min(hours, 6))
    points = await noaa.get_proton_flux_series(hours=hours)
    bands = [
        {"label": "S1", "pfu": 10.0},
        {"label": "S2", "pfu": 100.0},
        {"label": "S3", "pfu": 1000.0},
    ]
    return FluxSeries(points=points, tripwire_pfu=SPE_TRIPWIRE_PFU, s_scale_bands=bands)


@router.get("/api/telemetry/kp", response_model=KpSeries)
async def kp_history(points: int = 288):
    """Sampled planetary Kp history (1-minute source, max 288 points)."""
    points = max(24, min(points, 288))
    data = await noaa.get_kp_series(points=points)
    return KpSeries(points=data)


@router.post("/api/plan", response_model=PlanResult)
async def plan_mission_endpoint(mission: MissionProfile, crew: list[CrewMember]):
    """What-if mission planner: project dose, margins, max duration, verdict."""
    if not crew:
        raise HTTPException(status_code=422, detail="Provide at least one crew member")
    telemetry = await noaa.latest_snapshot()
    return PlanResult(**plan_mission(mission, crew, telemetry))


