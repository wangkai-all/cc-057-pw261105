"""One payload that powers the whole page.

Both states share one page: delivered orders (mean delivery time from the
completed set) and still-waiting orders (right-censored observations).  The
Kaplan–Meier curve is built only from non-cancelled orders; cancelled orders
are listed separately with a footnote stating the curve's scope.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .km import CensorMark, DayRisk, KMResult, Step, km_from_observations
from .model import build_observations, build_rows, parse_date, sort_rows


def _step_payload(step: Step) -> dict[str, Any]:
    return {
        "days": step.days,
        "survival": round(step.survival, 6),
        "at_risk": step.at_risk,
        "received": step.received,
        "censored": step.censored,
        "at_risk_orders": step.at_risk_orders,
        "received_orders": step.received_orders,
        "censored_orders": step.censored_orders,
    }


def _censor_payload(mark: CensorMark) -> dict[str, Any]:
    return {
        "days": mark.days,
        "survival": round(mark.survival, 6),
        "count": mark.count,
        "orders": mark.orders,
    }


def _day_payload(day: DayRisk) -> dict[str, Any]:
    return {
        "days": day.days,
        "at_risk": day.at_risk,
        "received": day.received,
        "censored": day.censored,
        "survival_after": round(day.survival_after, 6),
        "at_risk_orders": day.at_risk_orders,
        "received_orders": day.received_orders,
        "censored_orders": day.censored_orders,
    }


def _result_payload(result: KMResult) -> dict[str, Any]:
    return {
        "total": result.total,
        "completed": result.completed,
        "waiting": result.waiting,
        "steps": [_step_payload(s) for s in result.steps],
        "censor_marks": [_censor_payload(c) for c in result.censor_marks],
        "timeline": [_day_payload(d) for d in result.timeline],
        "points": result.points,
        "median_days": result.median_days,
        "p90_days": result.p90_days,
        "max_follow_up_days": result.max_follow_up_days,
        "completed_mean_days": result.completed_mean_days,
        "completed_median_days": result.completed_median_days,
        "waiting_mean_days": result.waiting_mean_days,
        "waiting_max_days": result.waiting_max_days,
    }


def analyse(orders: list[dict], as_of: date) -> dict[str, Any]:
    """Build the complete response for one (filters, cut-off) view.

    Orders placed after the cut-off are not yet in the book at that date and
    are dropped from every list rather than treated as errors.
    """
    orders = [
        o
        for o in orders
        if (parse_date(o.get("order_date")) or date.max) <= as_of
    ]
    observations = build_observations(orders, as_of)
    rows = sort_rows(build_rows(orders, as_of))
    km = km_from_observations(observations)

    cancelled = [r for r in rows if r["status"] == "cancelled"]
    completed = [r for r in rows if r["status"] == "completed"]
    waiting = [r for r in rows if r["status"] == "waiting"]

    return {
        "as_of": as_of.isoformat(),
        "km": _result_payload(km),
        "orders": rows,
        "cancelled_orders": cancelled,
        "completed_orders": completed,
        "waiting_orders": waiting,
        "counts": {
            "placed": len(rows),
            "completed": len(completed),
            "waiting": len(waiting),
            "cancelled": len(cancelled),
            "curve": km.total,
        },
    }
