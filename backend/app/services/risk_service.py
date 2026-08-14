"""Risk assessment against NASA exposure limits.

Verified limits (2026-08-12 browser research):
  - NASA-STD-3001 Vol 1 Rev C (via NASA OCHMO-TB-020):
      * Career Space Permissible Exposure Limit: 600 mSv effective dose,
        age/sex neutral (3% mean risk of cancer mortality).
      * Solar Particle Event limit: 250 mSv effective dose.
      * Nuclear technologies: 20 mSv per mission year.
  - NCRP Report 132 (scientific basis, granular age/sex career matrix):
      * 30-day: BFO 0.25 Gy-Eq, Eye 1.0 Gy-Eq, Skin 1.5 Gy-Eq.
      * Annual: BFO 0.50 Gy-Eq, Eye 2.0 Gy-Eq, Skin 3.0 Gy-Eq.
      * Career by age at first exposure:
          25y: M 0.7 Sv / F 0.4 Sv
          35y: M 1.0 Sv / F 0.6 Sv
          45y: M 1.5 Sv / F 0.9 Sv
          55y: M 3.0 Sv / F 1.7 Sv
"""
from app.models.schemas import CrewMember, MissionProfile, RiskReport, TelemetrySnapshot
from app.services.dose_engine import estimate_daily_dose

# Short-term / annual limits (NCRP 132, BFO reference values)
LIMIT_30D_MSV = 250.0
LIMIT_ANNUAL_MSV = 500.0

# NASA operational career limit (age/sex neutral)
NASA_CAREER_LIMIT_MSV = 600.0

# NCRP 132 career limits by age at first exposure (mSv): {age: (male, female)}
NCRP_CAREER_TABLE_MSV = {
    25: (700, 400),
    35: (1000, 600),
    45: (1500, 900),
    55: (3000, 1700),
}


def career_limit_mSv(age: int, sex: str, use_ncrp: bool = True) -> float:
    """Career limit for a crew member.

    NCRP 132 gives age/sex granularity; NASA's current operational policy is a
    flat 600 mSv. We report the NCRP value when available (more informative),
    falling back to the NASA 600 mSv default.
    """
    if not use_ncrp:
        return NASA_CAREER_LIMIT_MSV
    age_row = max((a for a in NCRP_CAREER_TABLE_MSV if a <= age), default=25)
    male, female = NCRP_CAREER_TABLE_MSV[age_row]
    return float(male if sex == "male" else female)


def assess(mission: MissionProfile, crew: list[CrewMember], telemetry: TelemetrySnapshot) -> list[RiskReport]:
    dose = estimate_daily_dose(mission, telemetry)
    # Simulated cumulative exposure: assumed uniform accumulation across the mission
    cumulative = dose.total_daily_msv * mission.duration_days

    reports: list[RiskReport] = []
    for member in crew:
        career = career_limit_mSv(member.age, member.sex)
        util_30d = dose.total_daily_msv * 30 / LIMIT_30D_MSV
        util_annual = (dose.total_daily_msv * 365) / LIMIT_ANNUAL_MSV
        util_career = cumulative / career

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
                limit_career_msv=career,
                utilization_30d=round(util_30d, 3),
                utilization_annual=round(util_annual, 3),
                utilization_career=round(util_career, 3),
                level=level,
                recommendation=rec,
            )
        )
    return reports
