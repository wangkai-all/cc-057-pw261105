"""Kaplan–Meier estimator for time-to-full-receipt.

Implemented directly from the product-limit formula rather than a stats
dependency:

    S(t) = Π_{u <= t} (1 - d_u / n_u)

where ``n_u`` is the risk set at event day ``u`` (orders neither received nor
censored *before* ``u``) and ``d_u`` the number of full receipts at ``u``.
Orders still waiting at the cut-off are right-censored at their elapsed wait
days.  Censoring on the same day as receipts is applied *after* the receipt
calculation, so those censored orders are still counted in the risk set for
that day's receipts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, median

from .model import Observation, ValidationError


@dataclass(frozen=True)
class Step:
    """One event day of the product-limit curve."""

    days: int
    survival: float
    at_risk: int
    received: int
    censored: int
    at_risk_orders: list[str] = field(default_factory=list)
    received_orders: list[str] = field(default_factory=list)
    censored_orders: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CensorMark:
    """A day on which orders left the risk set without being received."""

    days: int
    survival: float
    count: int
    orders: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DayRisk:
    """Per-day audit row, for every distinct wait day (events and/or censoring)."""

    days: int
    at_risk: int
    received: int
    censored: int
    survival_after: float
    at_risk_orders: list[str] = field(default_factory=list)
    received_orders: list[str] = field(default_factory=list)
    censored_orders: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KMResult:
    total: int
    completed: int
    waiting: int
    steps: list[Step]
    censor_marks: list[CensorMark]
    timeline: list[DayRisk]
    points: list[dict]
    median_days: int | None
    p90_days: int | None
    max_follow_up_days: int
    completed_mean_days: float | None
    completed_median_days: float | None
    waiting_mean_days: float | None
    waiting_max_days: int | None


def _percentile_step(steps: list[Step], target: float) -> int | None:
    """Smallest event day whose survival is at or below ``target``.

    ``None`` means the curve never gets there; callers must show "无法估计"
    rather than substitute zero.
    """
    for step in steps:
        if step.survival <= target + 1e-12:
            return step.days
    return None


def km_from_observations(observations: list[Observation]) -> KMResult:
    for obs in observations:
        if obs.duration < 0:
            raise ValidationError(f"order {obs.order_id}: negative wait duration")

    if not observations:
        return KMResult(
            total=0,
            completed=0,
            waiting=0,
            steps=[],
            censor_marks=[],
            timeline=[],
            points=[{"days": 0, "survival": 1.0}],
            median_days=None,
            p90_days=None,
            max_follow_up_days=0,
            completed_mean_days=None,
            completed_median_days=None,
            waiting_mean_days=None,
            waiting_max_days=None,
        )

    completed = [o for o in observations if o.event]
    waiting = [o for o in observations if not o.event]

    durations = sorted({o.duration for o in observations})
    steps: list[Step] = []
    censor_marks: list[CensorMark] = []
    timeline: list[DayRisk] = []
    survival = 1.0

    for days in durations:
        at_day = [o for o in observations if o.duration == days]
        events = [o for o in at_day if o.event]
        censored = [o for o in at_day if not o.event]
        at_risk = [o for o in observations if o.duration >= days]
        n = len(at_risk)
        if n == 0:  # pragma: no cover - at_day is non-empty by construction
            continue

        if events:
            # Receipts are computed first; same-day censoring still counts in
            # the denominator, then leaves the risk set.
            survival *= 1.0 - len(events) / n
            steps.append(
                Step(
                    days=days,
                    survival=survival,
                    at_risk=n,
                    received=len(events),
                    censored=len(censored),
                    at_risk_orders=[o.order_id for o in at_risk],
                    received_orders=[o.order_id for o in events],
                    censored_orders=[o.order_id for o in censored],
                )
            )

        if censored:
            censor_marks.append(
                CensorMark(
                    days=days,
                    survival=survival,
                    count=len(censored),
                    orders=[o.order_id for o in censored],
                )
            )

        timeline.append(
            DayRisk(
                days=days,
                at_risk=n,
                received=len(events),
                censored=len(censored),
                survival_after=survival,
                at_risk_orders=[o.order_id for o in at_risk],
                received_orders=[o.order_id for o in events],
                censored_orders=[o.order_id for o in censored],
            )
        )

    max_follow_up = max(o.duration for o in observations)
    points: list[dict] = [{"days": 0, "survival": 1.0}]
    for step in steps:
        points.append({"days": step.days, "survival": step.survival})
    if points[-1]["days"] < max_follow_up:
        points.append({"days": max_follow_up, "survival": survival})

    completed_durations = [o.duration for o in completed]
    waiting_durations = [o.duration for o in waiting]

    return KMResult(
        total=len(observations),
        completed=len(completed),
        waiting=len(waiting),
        steps=steps,
        censor_marks=censor_marks,
        timeline=timeline,
        points=points,
        median_days=_percentile_step(steps, 0.5),
        p90_days=_percentile_step(steps, 0.1),
        max_follow_up_days=max_follow_up,
        completed_mean_days=mean(completed_durations) if completed_durations else None,
        completed_median_days=(
            float(median(completed_durations)) if completed_durations else None
        ),
        waiting_mean_days=mean(waiting_durations) if waiting_durations else None,
        waiting_max_days=max(waiting_durations) if waiting_durations else None,
    )
