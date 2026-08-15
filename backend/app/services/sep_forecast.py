"""SEP onset forecast (heuristic).

Converts the latest GOES X-ray flare class into an estimate of the
probability that a solar particle event (>=10 pfu, >=10 MeV) starts within
the next WINDOW_H hours, plus an expected onset lead time after flare peak.

This is a decision-support heuristic informed by published SEP occurrence
statistics (NOAA/UMASEP-style analyses: the larger the flare, the higher the
probability and the faster the proton onset). It is NOT a validated physics
forecast and is labeled as such in the API and UI.
"""
from __future__ import annotations

from typing import Optional

WINDOW_H = 48

# (min_magnitude, probability, lead_hours, risk_level)
# magnitude = numeric part of the flare letter (X10 -> 10.0, M1.2 -> 0.12)
_TABLE = [
    (10.0, 0.75, 0.3, "severe"),   # X10+
    (5.0, 0.50, 0.5, "severe"),    # X5-X9
    (1.0, 0.25, 1.0, "high"),      # X1-X4
    (0.5, 0.08, 2.0, "moderate"),  # M5-M9
    (0.1, 0.02, 4.0, "low"),       # M1-M4
    (0.0, 0.01, 8.0, "low"),       # C and below / background
]

RISK_LABELS = {"low": "LOW", "moderate": "MODERATE", "high": "HIGH", "severe": "SEVERE"}


def parse_flare_class(flare_class: Optional[str]) -> Optional[float]:
    """Normalize a flare class to a comparable magnitude.

    'M1.2' -> 0.12, 'X3' -> 3.0, 'C2.1' -> 0.021, 'B5' -> 0.005.
    Returns None for missing/unknown input.
    """
    if not flare_class:
        return None
    s = str(flare_class).strip().upper()
    if not s or s[0] not in "ABCDMX":
        return None
    try:
        mag = float(s[1:])
    except ValueError:
        return None
    scale = {"X": 1.0, "M": 0.1, "C": 0.01, "B": 0.001, "A": 0.0001}
    return mag * scale.get(s[0], 0.0)


def forecast(flare_class: Optional[str]) -> dict:
    """SEP onset forecast for the latest GOES flare class."""
    mag = parse_flare_class(flare_class)
    prob, lead_h, risk = 0.01, 8.0, "low"
    if mag is not None:
        for threshold, p, lead, r in _TABLE:
            if mag >= threshold:
                prob, lead_h, risk = p, lead, r
                break
    return {
        "flare_class": flare_class,
        "probability": prob,
        "window_h": WINDOW_H,
        "lead_time_h": lead_h,
        "risk_level": risk,
        "risk_label": RISK_LABELS[risk],
        "basis": (
            "Heuristic from flare class (published SEP occurrence statistics); "
            "not a validated forecast."
        ),
    }
