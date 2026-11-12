from __future__ import annotations

from datetime import date

import pytest

from app.analysis import analyse
from app.km import km_from_observations
from app.model import (
    Observation,
    ValidationError,
    build_observations,
    build_rows,
    natural_days,
    status_at,
)


def order(oid, ordered, received=None, cancelled=None):
    return {
        "order_id": oid,
        "supplier": "S",
        "material": "M",
        "order_date": ordered,
        "full_receipt_date": received,
        "cancel_date": cancelled,
    }


def d(value: str) -> date:
    return date.fromisoformat(value)


def test_natural_days_calendar_not_business():
    assert natural_days(d("2026-01-05"), d("2026-01-19")) == 14
    assert natural_days(d("2026-02-01"), d("2026-02-13")) == 12
    # 2024 is a leap year; Feb 29 counts.
    assert natural_days(d("2024-02-28"), d("2024-03-01")) == 2
    assert natural_days(d("2026-06-30"), d("2026-07-01")) == 1


def test_status_ignores_future_receipt_and_future_cancel():
    o = order("X", "2026-01-01", received="2026-07-10")
    assert status_at(o, d("2026-06-30")) == "waiting"
    assert status_at(o, d("2026-07-10")) == "completed"
    assert status_at(o, d("2026-07-11")) == "completed"

    c = order("Y", "2026-01-01", cancelled="2026-07-20")
    assert status_at(c, d("2026-06-30")) == "waiting"
    assert status_at(c, d("2026-07-20")) == "cancelled"


def test_event_on_cutoff_counts_as_completed():
    o = order("Z", "2026-03-01", received="2026-06-30")
    assert status_at(o, d("2026-06-30")) == "completed"
    assert build_observations([o], d("2026-06-30"))[0] == Observation(
        "Z", 121, True, "S", "M"
    )


def test_cancelled_before_cutoff_excluded_from_curve_but_listed():
    o = order("C", "2026-01-15", cancelled="2026-02-14")
    rows = build_rows([o], d("2026-06-30"))
    assert rows[0]["status"] == "cancelled"
    assert rows[0]["wait_days"] == 30
    assert build_observations([o], d("2026-06-30")) == []


def test_order_after_cutoff_not_yet_placed():
    o = order("N", "2026-07-01")
    assert build_rows([o], d("2026-06-30")) == []
    assert build_observations([o], d("2026-06-30")) == []
    # analyse() drops it rather than failing: at that cut-off it is unplaced.
    payload = analyse([o], d("2026-06-30"))
    assert payload["orders"] == []
    assert payload["km"]["total"] == 0


def test_bad_dates_rejected():
    with pytest.raises(ValidationError, match="received before"):
        status_at(order("B", "2026-01-10", received="2026-01-01"), d("2026-06-30"))
    with pytest.raises(ValidationError, match="cancelled before"):
        status_at(order("B", "2026-01-10", cancelled="2026-01-01"), d("2026-06-30"))


def test_same_day_event_then_censoring():
    """Risk set includes same-day censored orders; events computed first."""
    obs = [
        Observation("E", 12, True),
        Observation("C", 12, False),
        Observation("L", 20, True),
    ]
    result = km_from_observations(obs)
    step = result.steps[0]
    assert step.days == 12
    assert step.at_risk == 3
    assert step.received == 1
    assert step.censored == 1
    assert step.survival == pytest.approx(2 / 3)

    assert result.steps[1].days == 20
    assert result.steps[1].at_risk == 1
    assert result.steps[1].survival == pytest.approx(0.0)
    assert result.censor_marks[0].days == 12
    assert result.censor_marks[0].count == 1
    assert "C" in result.censor_marks[0].orders


def test_censoring_only_day_keeps_curve_flat():
    obs = [Observation("E", 5, True), Observation("C", 5, False), Observation("W", 9, False)]
    result = km_from_observations(obs)
    assert len(result.steps) == 1
    assert result.steps[0].survival == pytest.approx(1 - 1 / 3)
    assert result.points[-1] == {"days": 9, "survival": pytest.approx(2 / 3)}


def test_median_and_p90_unestimable_return_none():
    obs = [Observation(str(i), 10, True) for i in range(2)]
    obs += [Observation("w1", 30, False), Observation("w2", 30, False)]
    result = km_from_observations(obs)
    # S only drops to 0 at day 10, so median is estimable but p90 is not.
    assert result.median_days == 10
    assert result.p90_days is None

    obs = [Observation("a", 10, True), Observation("b", 15, False), Observation("c", 15, False)]
    result = km_from_observations(obs)
    # S falls only to 2/3, so neither the median nor the 90th percentile is
    # reached: both must read as unavailable, not zero.
    assert result.steps[0].survival == pytest.approx(2 / 3)
    assert result.median_days is None
    assert result.p90_days is None


def test_completed_mean_is_separate_from_waiting():
    obs = [
        Observation("a", 10, True),
        Observation("b", 20, True),
        Observation("c", 40, False),
        Observation("d", 50, False),
    ]
    result = km_from_observations(obs)
    assert result.completed_mean_days == pytest.approx(15)
    assert result.waiting_mean_days == pytest.approx(45)
    assert result.waiting_max_days == 50
