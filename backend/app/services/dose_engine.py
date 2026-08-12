"""Dose estimation engine.

Model structure (physics-informed lookups):
  total_daily = GCR_baseline(orbit_type) + SPE_daily(proton_flux, duration)

TODO(verify): all constants below are PLACEHOLDERS pending verification against
NASA/NAIRAS published values. They are structured to be swapped for real numbers
without code changes.

Reference points to verify:
  - GCR dose rates: ~0.3-1.0 mSv/day in LEO (varies with altitude/inclination/
    solar cycle), ~1-2 mSv/day in deep space/lunar transit.
  - SPE dose: scales with integral proton flux (>10 MeV) and duration; a large
    SPE (e.g. Oct 2003) can deliver tens-hundreds of mSv unshielded.
"""
from dataclasses import dataclass

from app.models.schemas import MissionProfile, TelemetrySnapshot

# Placeholder GCR baselines (mSv/day) — TODO(verify)
GCR_BASELINE_MSV_PER_DAY: dict[str, float] = {
    "leo_iss": 0.35,       # ~400 km, 51.6 deg
    "leo_polar": 0.60,     # higher-latitude crossings
    "lunar_transit": 1.10,
    "deep_space": 1.80,    # Mars transit approx
}

# Placeholder SPE dose coefficient: mSv per (pfu * hour) — TODO(verify/calibrate)
SPE_DOSE_COEFFICIENT = 1.5e-4  # extremely rough; calibrate against published SPE doses

# SPE flux threshold (pfu) above which we consider an event ongoing
SPE_TRIPWIRE_PFU = 10.0


@dataclass
class DoseResult:
    gcr_daily_msv: float
    spe_daily_msv: float
    total_daily_msv: float
    projected_total_msv: float
    notes: list[str]


def estimate_daily_dose(mission: MissionProfile, telemetry: TelemetrySnapshot) -> DoseResult:
    notes: list[str] = []
    gcr_daily = GCR_BASELINE_MSV_PER_DAY.get(mission.orbit_type, 0.5)

    spe_daily = 0.0
    flux = telemetry.spe_proton_flux
    if flux is not None:
        # If flux is above tripwire, assume event ongoing for a fraction of the day
        event_hours = 24.0 if flux >= SPE_TRIPWIRE_PFU else 0.0
        spe_daily = flux * SPE_DOSE_COEFFICIENT * event_hours
        if flux >= SPE_TRIPWIRE_PFU:
            notes.append(f"Solar particle event in progress (proton flux {flux:.1f} pfu).")

    total_daily = gcr_daily + spe_daily
    projected_total = total_daily * mission.duration_days
    notes.append("Constants are placeholders pending verification (see dose_engine.py TODO).")
    return DoseResult(
        gcr_daily_msv=gcr_daily,
        spe_daily_msv=round(spe_daily, 4),
        total_daily_msv=round(total_daily, 4),
        projected_total_msv=round(projected_total, 2),
        notes=notes,
    )
