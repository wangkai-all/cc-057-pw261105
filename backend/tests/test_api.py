from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_filters(client):
    body = client.get("/api/filters").json()
    assert "华东精密" in body["suppliers"]
    assert "轴承" in body["materials"]
    assert body["min_cutoff"] == "2026-01-05"


def test_analysis_defaults_to_last_event(client):
    body = client.get("/api/analysis").json()
    assert body["as_of"] == "2026-07-20"
    assert body["counts"]["cancelled"] == 4
    assert body["filters"] == {"supplier": None, "material": None}


def test_cutoff_flip_changes_future_events(client):
    early = client.get("/api/analysis", params={"as_of": "2026-06-30"}).json()
    late = client.get("/api/analysis", params={"as_of": "2026-07-31"}).json()

    early_ids = {o["order_id"]: o for o in early["orders"]}
    late_ids = {o["order_id"]: o for o in late["orders"]}

    # F-6001 received after 06-30 -> waiting then completed.
    assert early_ids["F-6001"]["status"] == "waiting"
    assert early_ids["F-6001"]["future_receipt_ignored"] is True
    assert late_ids["F-6001"]["status"] == "completed"
    assert late_ids["F-6001"]["wait_days"] == 131

    # F-6002 cancelled after 06-30 -> still on the curve then excluded.
    assert early_ids["F-6002"]["status"] == "waiting"
    assert early_ids["F-6002"]["future_cancel_ignored"] is True
    assert late_ids["F-6002"]["status"] == "cancelled"

    # G-7001 received exactly on 06-30 -> completed at that cut-off.
    assert early_ids["G-7001"]["status"] == "completed"
    assert early_ids["G-7001"]["wait_days"] == 121


def test_cancelled_excluded_from_curve(client):
    body = client.get("/api/analysis", params={"as_of": "2026-06-30"}).json()
    curve = body["km"]
    all_steps = {o for s in curve["steps"] for o in s["at_risk_orders"]}
    cancelled_ids = {o["order_id"] for o in body["cancelled_orders"]}
    assert cancelled_ids == {"E-5001", "E-5002", "E-5003"}
    assert not (cancelled_ids & all_steps)
    assert body["counts"]["curve"] == len(all_steps)


def test_same_day_event_and_censor(client):
    body = client.get("/api/analysis", params={"as_of": "2026-06-30"}).json()
    step = next(s for s in body["km"]["steps"] if s["days"] == 12)
    assert "C-3001" in step["received_orders"]
    assert "C-3002" in step["censored_orders"]
    assert step["at_risk"] == body["counts"]["curve"]
    censor = next(c for c in body["km"]["censor_marks"] if c["days"] == 12)
    assert censor["orders"] == ["C-3002"]
    # C-3002 appears in the risk set of the day-12 step.
    assert "C-3002" in step["at_risk_orders"]


def test_percentile_unestimable_is_null_not_zero(client):
    body = client.get("/api/analysis", params={"as_of": "2026-06-30"}).json()
    assert body["km"]["median_days"] == 90
    assert body["km"]["p90_days"] is None

    narrow = client.get(
        "/api/analysis", params={"as_of": "2026-06-30", "supplier": "西部仪表"}
    ).json()
    assert narrow["km"]["median_days"] is None
    assert narrow["km"]["p90_days"] is None


def test_completed_mean_only_from_completed(client):
    body = client.get("/api/analysis", params={"as_of": "2026-06-30"}).json()
    completed = [o for o in body["orders"] if o["status"] == "completed"]
    waiting = [o for o in body["orders"] if o["status"] == "waiting"]
    assert body["km"]["completed_mean_days"] == pytest.approx(
        sum(o["wait_days"] for o in completed) / len(completed)
    )
    assert body["km"]["waiting_mean_days"] == pytest.approx(
        sum(o["wait_days"] for o in waiting) / len(waiting)
    )


def test_supplier_filter_scopes_everything(client):
    body = client.get(
        "/api/analysis", params={"as_of": "2026-06-30", "supplier": "华东精密"}
    ).json()
    assert {o["supplier"] for o in body["orders"]} == {"华东精密"}
    assert all(s["supplier"] == "华东精密" for s in body["orders"])


def test_invalid_cutoff_rejected(client):
    r = client.get("/api/analysis", params={"as_of": "2026-01-01"})
    assert r.status_code == 422
    r = client.get("/api/analysis", params={"as_of": "not-a-date"})
    assert r.status_code == 422
