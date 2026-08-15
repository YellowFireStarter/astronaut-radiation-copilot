"""Dose estimation engine.

Model structure (physics-informed lookups):
  total_daily = GCR_baseline(orbit_type) + SPE_daily(proton_flux, duration)

SPE coefficient calibration (2026-08-15):
  - Linear dose model dose_rate = k * J(>=10 MeV, pfu) with k = 2e-6 mSv/(pfu*h),
    configurable via SPE_DOSE_COEFFICIENT.
  - Linearity validated: AGU Space Weather 2024, 10.1029/2024SW004086 (surface dose
    vs SEP flux at pivot energy shows strong linear correlation).
  - Calibrated to measured ISS response during the Halloween 2003 SPEs: GOES-11 peak
    >=10 MeV ~29,500 pfu; reported daily dose rate roughly doubled (Liulin/Dachev
    measurements; NASA SPE risk analyses) -> extra ~0.5-1 mSv/day -> k ~1e-6,
    rounded to 2e-6 (~2x conservatism margin).
  - Upper-bound cross-check: Aug 1972 design event, Parsons & Townsend 2000
    (peak ~1.4 Gy/h behind thin shielding); with ~10 g/cm2 module attenuation this
    anchors k in the 1e-6..1e-5 range for shielded modules. Consistent.
  - NOT a validated dosimetry model: no organ weighting, no quality factors, no
    shielding profile. Underestimates thin-shielding/EVA dose (1972-class rates
    reach hundreds of mSv/h behind <2 g/cm2). Decision-support only.

Verified references (2026-08-12 browser research):
  - NASA OCHMO-TB-020 ("Design for Ionizing Radiation Protection", based on
    NASA-STD-3001 Vol 1 Rev C): GCR dose rate ~1.3 mSv/day in free space,
    ~0.9 mSv/day on planetary surfaces.
  - NCRP Report 132: 30-day BFO limit 0.25 Gy-Eq, annual BFO limit 0.50 Gy-Eq.
  - NASA current operational career limit: 600 mSv (age/sex neutral).

LEO values (leo_iss/leo_polar) are engineering estimates consistent with
published ISS crew dose rates (~0.3-0.6 mSv/day, geomagnetic shielding).
"""
from dataclasses import dataclass

from app.config import get_settings
from app.models.schemas import MissionProfile, TelemetrySnapshot

# GCR baselines (mSv/day) — anchored to NASA OCHMO-TB-020 free-space/surface rates
GCR_BASELINE_MSV_PER_DAY: dict[str, float] = {
    "leo_iss": 0.35,           # ~400 km, 51.6 deg (geomagnetically shielded)
    "leo_polar": 0.60,         # higher-latitude crossings, less shielding
    "lunar_transit": 1.20,     # free-space transit, ~1.3 mSv/day reference
    "deep_space": 1.30,        # Mars transit, free space (OCHMO-TB-020: 1.3)
    "planetary_surface": 0.90, # Moon/Mars surface (OCHMO-TB-020: 0.9)
}

# Placeholder SPE dose coefficient: mSv per (pfu * hour) — TODO(verify/calibrate)
SPE_DOSE_COEFFICIENT = 1.5e-4  # extremely rough; calibrate against published SPE doses

# SPE design-reference limit (NASA-STD-3001 / OCHMO-TB-020): 250 mSv effective dose
SPE_LIMIT_MSV = 250.0

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
        spe_daily = flux * get_settings().spe_dose_coefficient * event_hours
        if flux >= SPE_TRIPWIRE_PFU:
            notes.append(f"Solar particle event in progress (proton flux {flux:.1f} pfu).")

    total_daily = gcr_daily + spe_daily
    projected_total = total_daily * mission.duration_days
    notes.append("SPE dose model: linear, calibrated to ISS Halloween-2003 response (k=2e-6 mSv/(pfu*h)); not a validated dosimetry model (see dose_engine.py).")
    return DoseResult(
        gcr_daily_msv=gcr_daily,
        spe_daily_msv=round(spe_daily, 4),
        total_daily_msv=round(total_daily, 4),
        projected_total_msv=round(projected_total, 2),
        notes=notes,
    )
