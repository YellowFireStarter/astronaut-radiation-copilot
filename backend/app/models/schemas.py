"""Pydantic schemas for the Radiation Copilot API."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MissionProfile(BaseModel):
    name: str = Field(default="Untitled mission", max_length=120)
    orbit_type: Literal["leo_iss", "leo_polar", "lunar_transit", "deep_space", "planetary_surface"] = "leo_iss"
    altitude_km: Optional[float] = Field(default=None, ge=0, description="Orbit altitude (LEO)")
    inclination_deg: Optional[float] = Field(default=None, ge=-90, le=90)
    start_date: date = Field(default_factory=date.today)
    duration_days: int = Field(default=30, ge=1, le=730)


class CrewMember(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    age: int = Field(ge=18, le=75)
    sex: Literal["male", "female"] = "male"


class TelemetrySnapshot(BaseModel):
    time_tag: Optional[datetime] = None
    kp_index: Optional[float] = None
    estimated_kp: Optional[float] = None
    solar_wind_bt: Optional[float] = None
    solar_wind_bz_gsm: Optional[float] = None
    solar_wind_speed_km_s: Optional[float] = None
    spe_proton_flux: Optional[float] = Field(default=None, description="Integral proton flux >= 10 MeV (pfu, NOAA S-scale basis)")
    xray_flare_class: Optional[str] = None
    sources_ok: bool = True
    degraded: bool = False


class DoseBreakdown(BaseModel):
    gcr_daily_msv: float
    spe_daily_msv: float
    total_daily_msv: float
    projected_total_msv: float


class DoseForecast(BaseModel):
    mission: MissionProfile
    breakdown: DoseBreakdown
    notes: list[str] = []


class RiskReport(BaseModel):
    crew: CrewMember
    cumulative_msv: float
    limit_30d_msv: float
    limit_annual_msv: float
    limit_career_msv: float
    utilization_30d: float
    utilization_annual: float
    utilization_career: float
    level: Literal["green", "yellow", "red"]
    recommendation: str


class RiskAssessment(BaseModel):
    mission: MissionProfile
    reports: list[RiskReport]


class BriefRequest(BaseModel):
    mission: MissionProfile
    crew: list[CrewMember] = Field(default_factory=list, max_length=6)
    kind: Literal["daily", "alert"] = "daily"
    telemetry: Optional[TelemetrySnapshot] = None


class BriefResponse(BaseModel):
    kind: str
    text: str
    llm_used: bool = False
    provider: str = "none"

class FluxPoint(BaseModel):
    time_tag: str
    flux_pfu: float


class FluxSeries(BaseModel):
    points: list[FluxPoint] = []
    tripwire_pfu: float
    s_scale_bands: list[dict] = []
    source: str


class KpPoint(BaseModel):
    time_tag: str
    kp_index: float


class KpSeries(BaseModel):
    points: list[KpPoint] = []
    source: str


class SpeAlert(BaseModel):
    level: Literal["nominal", "watch", "warning", "emergency"] = "nominal"
    level_index: int = 0
    flux_pfu: Optional[float] = None
    s_scale: str = "S0"
    flare_class: Optional[str] = None
    tripwire_pfu: float = 10.0
    action: str = ""
    time_tag: Optional[datetime] = None
    forecast: Optional[SepForecast] = None


class SepForecast(BaseModel):
    flare_class: Optional[str] = None
    probability: float = 0.01
    window_h: int = 48
    lead_time_h: float = 8.0
    risk_level: Literal["low", "moderate", "high", "severe"] = "low"
    risk_label: str = "LOW"
    basis: str = ""


class PlanCrewReport(BaseModel):
    name: str
    age: int
    sex: str
    career_limit_msv: float
    projected_msv: float
    utilization_career: float
    utilization_30d: float
    utilization_annual: float


class PlanResult(BaseModel):
    mission: MissionProfile
    crew_reports: list[PlanCrewReport]
    worst_utilization: float
    projected_total_msv: float
    max_duration_days: int
    spe_alert: SpeAlert
    verdict: Literal["feasible", "caution", "infeasible"]
    notes: list[str] = []
