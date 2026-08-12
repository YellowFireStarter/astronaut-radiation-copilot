"""Risk assessment against NASA exposure limits.

TODO(verify): limit table below is a PLACEHOLDER pending verification of
NASA-STD-3001 / NCRP values. Real limits vary by age and sex (career limits).
Structure is ready for a per-age/sex table.
"""
from app.models.schemas import CrewMember, RiskReport
from app.services.dose_engine import estimate_daily_dose
from app.models.schemas import MissionProfile, TelemetrySnapshot

# Placeholder limits (mSv) — TODO(verify)
LIMIT_30D_MSV = 250.0
LIMIT_ANNUAL_MSV = 500.0
LIMIT_CAREER_MSV = 600.0  # flat placeholder; real value is age/sex dependent


def assess(mission: MissionProfile, crew: list[CrewMember], telemetry: TelemetrySnapshot) -> list[RiskReport]:
    dose = estimate_daily_dose(mission, telemetry)
    # Simulated cumulative exposure: assumed uniform accumulation across the mission
    cumulative = dose.total_daily_msv * mission.duration_days

    reports: list[RiskReport] = []
    for member in crew:
        util_30d = dose.total_daily_msv * 30 / LIMIT_30D_MSV
        util_annual = (dose.total_daily_msv * 365) / LIMIT_ANNUAL_MSV
        util_career = cumulative / LIMIT_CAREER_MSV

        worst = max(util_30d, util_annual, util_career)
        if worst >= 0.8:
            level, rec = "red", "Exposure budget nearly exhausted — escalate to flight surgeon and replan mission profile."
        elif worst >= 0.5:
            level, rec = "yellow", "Elevated exposure — review EVA schedule and consider radiation sheltering windows."
        else:
            level, rec = "green", "Within limits — continue nominal operations."

        reports.append(
            RiskReport(
                crew=member,
                cumulative_msv=round(cumulative, 2),
                limit_30d_msv=LIMIT_30D_MSV,
                limit_annual_msv=LIMIT_ANNUAL_MSV,
                limit_career_msv=LIMIT_CAREER_MSV,
                utilization_30d=round(util_30d, 3),
                utilization_annual=round(util_annual, 3),
                utilization_career=round(util_career, 3),
                level=level,
                recommendation=rec,
            )
        )
    return reports
