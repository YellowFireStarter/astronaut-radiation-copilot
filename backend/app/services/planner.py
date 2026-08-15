"""What-if mission planner.

Projects cumulative crew dose for a candidate mission profile and reports
margin against the 30-day, annual, and career limits, plus the current SPE
alert overlay. Answers: "how long can we fly this profile before hitting
80% of the crew's career budget?"
"""
from __future__ import annotations

from app.models.schemas import CrewMember, MissionProfile
from app.services import spe_alert
from app.services.dose_engine import GCR_BASELINE_MSV_PER_DAY, SPE_DOSE_COEFFICIENT, SPE_TRIPWIRE_PFU, estimate_daily_dose
from app.services.risk_service import LIMIT_30D_MSV, LIMIT_ANNUAL_MSV, career_limit_mSv

# Utilization at which a profile is flagged as caution / infeasible
CAUTION_UTIL = 0.5
INFEASIBLE_UTIL = 0.8


def _current_spe_daily_msv(flux_pfu: float) -> float:
    """Daily SPE dose contribution under current conditions (dose_engine model)."""
    if flux_pfu is None or flux_pfu < SPE_TRIPWIRE_PFU:
        return 0.0
    return flux_pfu * SPE_DOSE_COEFFICIENT * 24.0


def max_duration_days(orbit_type: str, crew: list[CrewMember], spe_daily_msv: float, util_target: float = 0.8) -> int:
    """Longest mission (days) before the most-exposed crew member hits util_target of career limit."""
    gcr_daily = GCR_BASELINE_MSV_PER_DAY.get(orbit_type, 0.5)
    daily = gcr_daily + spe_daily_msv
    if daily <= 0:
        return 730
    longest = 730
    for member in crew:
        budget = career_limit_mSv(member.age, member.sex) * util_target
        days = int(budget / daily)
        longest = min(longest, max(days, 1))
    return longest


def plan(mission: MissionProfile, crew: list[CrewMember], telemetry) -> dict:
    """Produce a plan report for the candidate mission."""
    dose = estimate_daily_dose(mission, telemetry)
    alert = spe_alert.evaluate(telemetry)

    cumulative = dose.total_daily_msv * mission.duration_days
    # Utilization is evaluated against the mission's ACTUAL exposure windows:
    # a 30-day mission only consumes a 30-day slice of the 30-day/annual limits.
    window_30d = dose.total_daily_msv * min(mission.duration_days, 30)
    window_annual = dose.total_daily_msv * min(mission.duration_days, 365)
    reports = []
    worst_util = 0.0
    for member in crew:
        career = career_limit_mSv(member.age, member.sex)
        util_career = cumulative / career
        util_30d = window_30d / LIMIT_30D_MSV
        util_annual = window_annual / LIMIT_ANNUAL_MSV
        worst_util = max(worst_util, util_career, util_30d, util_annual)
        reports.append({
            "name": member.name,
            "age": member.age,
            "sex": member.sex,
            "career_limit_msv": round(career, 1),
            "projected_msv": round(cumulative, 2),
            "utilization_career": round(util_career, 3),
            "utilization_30d": round(util_30d, 3),
            "utilization_annual": round(util_annual, 3),
        })

    max_days = max_duration_days(mission.orbit_type, crew, _current_spe_daily_msv(telemetry.spe_proton_flux))

    # Verdict: SPE emergency or budget exhaustion => infeasible; elevated => caution
    if alert["level"] == "emergency" or worst_util >= INFEASIBLE_UTIL:
        verdict = "infeasible"
    elif alert["level"] in ("watch", "warning") or worst_util >= CAUTION_UTIL:
        verdict = "caution"
    else:
        verdict = "feasible"

    notes = [
        f"GCR baseline for {mission.orbit_type}: {GCR_BASELINE_MSV_PER_DAY.get(mission.orbit_type, 0.5)} mSv/day (NASA OCHMO-TB-020 anchored).",
        f"Max duration before 80% of most-exposed crew career budget: {max_days} days.",
        f"Current SPE status: {alert['level']} ({alert['s_scale']}, flux {alert['flux_pfu'] if alert['flux_pfu'] is not None else 'n/a'} pfu).",
    ]
    if mission.duration_days > max_days:
        notes.append("Candidate duration exceeds the 80% career-budget window - consider a shorter profile or different orbit.")

    return {
        "mission": mission,
        "crew_reports": reports,
        "worst_utilization": round(worst_util, 3),
        "projected_total_msv": round(cumulative, 2),
        "max_duration_days": max_days,
        "spe_alert": alert,
        "verdict": verdict,
        "notes": notes,
    }

