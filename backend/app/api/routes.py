"""API routes."""
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import (
    BriefRequest,
    BriefResponse,
    CrewMember,
    DoseForecast,
    MissionProfile,
    RiskAssessment,
    TelemetrySnapshot,
)
from app.services import risk_service
from app.services.brief_generator import generate_brief
from app.services.dose_engine import estimate_daily_dose
from app.services.noaa_client import NOAAClient

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
