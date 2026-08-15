"""Solar particle event (SPE) alert engine.

Maps current proton flux and flare activity onto an alert level aligned with
the NOAA S-scale (S1-S5) and the NASA SPE design limit (250 mSv effective).

Thresholds (integral flux >= 10 MeV, pfu):
  <10      nominal   (S0, background)
  10-99    watch     (S1, minor)  - SPE tripwire crossed
  100-999  warning   (S2, moderate)
  >=1000   emergency (S3+, strong to severe)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.schemas import TelemetrySnapshot

# SPE tripwire (pfu) - an event is considered ongoing above this
SPE_TRIPWIRE_PFU = 10.0

# NOAA S-scale bands (>= 10 MeV integral flux, pfu)
S_SCALE_BANDS = [
    ("S1", 10.0),
    ("S2", 100.0),
    ("S3", 1000.0),
    ("S4", 10000.0),
    ("S5", 100000.0),
]

ALERT_LEVELS = ("nominal", "watch", "warning", "emergency")

ACTIONS = {
    "nominal": "No solar particle event detected. Continue nominal operations.",
    "watch": "SPE tripwire crossed: monitor proton flux, review radiation sheltering plan, and pause non-critical EVAs.",
    "warning": "Elevated SPE conditions: shelter crew in radiation-safe modules, suspend EVAs, and re-evaluate mission timeline.",
    "emergency": "Severe SPE conditions: enforce full radiation sheltering, protect crew from acute exposure (NASA SPE limit 250 mSv).",
}


def s_scale_for_flux(flux_pfu: float) -> str:
    """Return the NOAA S-scale label for the given >=10 MeV flux."""
    label = "S0"
    for name, threshold in S_SCALE_BANDS:
        if flux_pfu >= threshold:
            label = name
    return label


def evaluate(telemetry: TelemetrySnapshot) -> dict:
    """Evaluate alert level from a telemetry snapshot."""
    flux = telemetry.spe_proton_flux
    flare = (telemetry.xray_flare_class or "").upper()

    if flux is None:
        level = "nominal"
        flux_pfu = None
    elif flux < SPE_TRIPWIRE_PFU:
        level = "nominal"
        flux_pfu = round(flux, 2)
    elif flux < 100:
        level = "watch"
        flux_pfu = round(flux, 2)
    elif flux < 1000:
        level = "warning"
        flux_pfu = round(flux, 1)
    else:
        level = "emergency"
        flux_pfu = round(flux, 1)

    # X-class flares are a leading indicator: at minimum a watch
    if flare.startswith("X"):
        if ALERT_LEVELS.index(level) < ALERT_LEVELS.index("watch"):
            level = "watch"

    return {
        "level": level,
        "level_index": ALERT_LEVELS.index(level),
        "flux_pfu": flux_pfu,
        "s_scale": s_scale_for_flux(flux) if flux is not None else "S0",
        "flare_class": telemetry.xray_flare_class,
        "tripwire_pfu": SPE_TRIPWIRE_PFU,
        "action": ACTIONS[level],
        "time_tag": telemetry.time_tag or datetime.utcnow(),
    }
