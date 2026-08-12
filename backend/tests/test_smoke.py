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
