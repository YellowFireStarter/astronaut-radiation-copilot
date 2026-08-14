"""Smoke tests — no external network required."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_limits():
    resp = client.get("/api/limits")
    assert resp.status_code == 200
    body = resp.json()
    assert body["30_day_msv"] > 0
    assert body["annual_msv"] > body["30_day_msv"]


def test_dose_forecast_offline():
    # Mission-only forecast; dose engine must not depend on network.
    resp = client.post(
        "/api/dose/forecast",
        json={"name": "Test mission", "orbit_type": "leo_iss", "duration_days": 30},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["breakdown"]["total_daily_msv"] > 0
    assert body["breakdown"]["projected_total_msv"] > 0


def test_risk_assess_requires_crew():
    resp = client.post("/api/risk/assess", json={"mission": {}})
    assert resp.status_code in (422, 500)  # 422 when schema requires crew list


def test_career_limit_lookup():
    from app.services.risk_service import career_limit_mSv, NASA_CAREER_LIMIT_MSV
    # NCRP matrix: 25y female = 400 mSv, 35y male = 1000 mSv
    assert career_limit_mSv(25, "female") == 400
    assert career_limit_mSv(35, "male") == 1000
    # NASA operational default when NCRP not used
    assert career_limit_mSv(40, "male", use_ncrp=False) == NASA_CAREER_LIMIT_MSV
    # Age below 25 clamps to the 25y row
    assert career_limit_mSv(20, "male") == 700
