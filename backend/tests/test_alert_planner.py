"""Tests for the SPE alert engine and what-if mission planner. No network required."""
from datetime import datetime, timezone

from app.models.schemas import CrewMember, MissionProfile, TelemetrySnapshot
from app.services import planner, spe_alert
from app.services.risk_service import career_limit_mSv


def _snapshot(flux=None, flare=None):
    return TelemetrySnapshot(
        time_tag=datetime.now(timezone.utc),
        kp_index=2.0,
        spe_proton_flux=flux,
        xray_flare_class=flare,
        sources_ok=True,
        degraded=False,
    )


def test_alert_nominal_below_tripwire():
    alert = spe_alert.evaluate(_snapshot(flux=1.2))
    assert alert["level"] == "nominal"
    assert alert["s_scale"] == "S0"


def test_alert_watch_at_tripwire():
    alert = spe_alert.evaluate(_snapshot(flux=10.0))
    assert alert["level"] == "watch"
    assert alert["s_scale"] == "S1"


def test_alert_warning_at_100():
    alert = spe_alert.evaluate(_snapshot(flux=150.0))
    assert alert["level"] == "warning"
    assert alert["s_scale"] == "S2"


def test_alert_emergency_at_1000():
    alert = spe_alert.evaluate(_snapshot(flux=2500.0))
    assert alert["level"] == "emergency"
    assert alert["s_scale"] == "S3"


def test_x_class_flare_raises_to_watch():
    alert = spe_alert.evaluate(_snapshot(flux=3.0, flare="X1.2"))
    assert alert["level"] == "watch"


def test_x_class_flare_does_not_downgrade_higher_level():
    alert = spe_alert.evaluate(_snapshot(flux=500.0, flare="X9.9"))
    assert alert["level"] == "warning"


def test_planner_feasible_short_leo():
    mission = MissionProfile(name="LEO check", orbit_type="leo_iss", duration_days=30)
    crew = [CrewMember(name="A", age=40, sex="male")]
    result = planner.plan(mission, crew, _snapshot(flux=1.0))
    assert result["verdict"] == "feasible"
    assert result["worst_utilization"] < 0.5
    assert result["max_duration_days"] > 30


def test_planner_infeasible_when_over_budget():
    # Deep space at ~1.3 mSv/day for 730 days vs 700 mSv career (25y male)
    mission = MissionProfile(name="Mars one-way", orbit_type="deep_space", duration_days=730)
    crew = [CrewMember(name="A", age=25, sex="male")]
    result = planner.plan(mission, crew, _snapshot(flux=1.0))
    assert result["worst_utilization"] >= 0.8
    assert result["verdict"] == "infeasible"


def test_planner_emergency_spe_overlay():
    mission = MissionProfile(name="SPE storm", orbit_type="lunar_transit", duration_days=14)
    crew = [CrewMember(name="A", age=45, sex="female")]
    result = planner.plan(mission, crew, _snapshot(flux=2500.0))
    assert result["spe_alert"]["level"] == "emergency"
    assert result["verdict"] == "infeasible"


def test_planner_max_duration_respects_youngest_female_budget():
    mission = MissionProfile(name="x", orbit_type="leo_polar", duration_days=30)
    crew = [CrewMember(name="M", age=45, sex="male"), CrewMember(name="F", age=25, sex="female")]
    result = planner.plan(mission, crew, _snapshot(flux=1.0))
    # 25y female career budget = 400 mSv; at 0.6 mSv/day * 0.8 -> ~533 days cap
    assert 100 <= result["max_duration_days"] <= 533


def test_career_limit_consistent_with_planner():
    assert career_limit_mSv(25, "female") == 400.0
    assert career_limit_mSv(55, "male") == 3000.0


def test_sep_forecast_parse_and_table():
    from app.services.sep_forecast import forecast, parse_flare_class
    assert parse_flare_class("M1.2") == 0.12
    assert parse_flare_class("X3") == 3.0
    assert parse_flare_class("C2.1") == 0.021
    assert parse_flare_class(None) is None
    f = forecast("X1.5")
    assert f["probability"] == 0.25
    assert f["risk_level"] == "high"
    assert f["window_h"] == 48


def test_sep_forecast_levels():
    from app.services.sep_forecast import forecast
    assert forecast(None)["risk_level"] == "low"
    assert forecast("C1.0")["risk_level"] == "low"
    assert forecast("M6.0")["risk_level"] == "moderate"
    assert forecast("X10.0")["risk_level"] == "severe"
    assert forecast("X10.0")["probability"] == 0.75


def test_spe_alert_includes_forecast():
    alert = spe_alert.evaluate(_snapshot(flux=5.0))
    assert "forecast" in alert
    assert alert["forecast"]["window_h"] == 48
