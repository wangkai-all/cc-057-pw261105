from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

OrderStatus = Literal["completed", "waiting", "cancelled"]


class ValidationError(ValueError):
    """Raised when an input date or as-of date is not usable."""


@dataclass(frozen=True)
class Observation:
    """One order reduced to what the survival estimator needs.

    ``event`` is True when the order reached full receipt at ``duration``
    days after ordering; False means right-censored (still waiting) at the
    cut-off.
    """

    order_id: str
    duration: int
    event: bool
    supplier: str | None = None
    material: str | None = None


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def natural_days(start: date, end: date) -> int:
    """Whole calendar days between two dates; negative if ``end`` precedes."""
    return (end - start).days


def status_at(order: dict, as_of: date) -> OrderStatus:
    """State of one order restored at the cut-off.

    - cancelled if cancellation happened on or before the cut-off,
    - completed if full receipt happened on or before the cut-off and the
      order was not cancelled before/at the cut-off,
    - waiting otherwise.

    Receipts and cancellations dated after the cut-off are future
    information and are ignored rather than applied early.
    """
    ordered = parse_date(order.get("order_date"))
    if ordered is None:
        raise ValidationError(f"order {order.get('order_id')}: missing order_date")
    if ordered > as_of:
        raise ValidationError(
            f"order {order.get('order_id')}: ordered after the as-of date"
        )

    cancelled = parse_date(order.get("cancel_date"))
    received = parse_date(order.get("full_receipt_date"))

    if cancelled is not None and cancelled <= as_of:
        if cancelled < ordered:
            raise ValidationError(
                f"order {order.get('order_id')}: cancelled before it was ordered"
            )
        return "cancelled"

    if received is not None and received <= as_of:
        if received < ordered:
            raise ValidationError(
                f"order {order.get('order_id')}: received before it was ordered"
            )
        return "completed"
    return "waiting"


def build_observations(orders: list[dict], as_of: date) -> list[Observation]:
    """One observation per order placed by the cut-off, minus cancellations."""
    out: list[Observation] = []
    for order in orders:
        ordered = parse_date(order.get("order_date"))
        if ordered is None:
            raise ValidationError(f"order {order.get('order_id')}: missing order_date")
        if ordered > as_of:
            continue  # not yet placed at this cut-off
        status = status_at(order, as_of)
        if status == "cancelled":
            continue  # cancelled before the cut-off: outside the curve
        if status == "completed":
            received = parse_date(order.get("full_receipt_date"))
            assert received is not None
            duration = natural_days(ordered, received)
            event = True
        else:
            duration = natural_days(ordered, as_of)
            event = False
        out.append(
            Observation(
                order_id=str(order.get("order_id")),
                duration=duration,
                event=event,
                supplier=order.get("supplier"),
                material=order.get("material"),
            )
        )
    return out


def build_rows(orders: list[dict], as_of: date) -> list[dict]:
    """Audit rows: raw dates plus the state restored at the cut-off."""
    rows: list[dict] = []
    for order in orders:
        ordered = parse_date(order.get("order_date"))
        if ordered is None:
            raise ValidationError(f"order {order.get('order_id')}: missing order_date")
        if ordered > as_of:
            continue
        status = status_at(order, as_of)
        received = parse_date(order.get("full_receipt_date"))
        cancelled = parse_date(order.get("cancel_date"))

        if status == "completed":
            wait = natural_days(ordered, received)  # type: ignore[arg-type]
            observed_at = received
        elif status == "cancelled":
            wait = natural_days(ordered, cancelled)  # type: ignore[arg-type]
            observed_at = cancelled
        else:
            wait = natural_days(ordered, as_of)
            observed_at = None

        rows.append(
            {
                "order_id": str(order.get("order_id")),
                "supplier": order.get("supplier"),
                "material": order.get("material"),
                "order_date": ordered.isoformat(),
                "full_receipt_date": received.isoformat() if received else None,
                "cancel_date": cancelled.isoformat() if cancelled else None,
                "status": status,
                "wait_days": wait,
                "observed_at": observed_at.isoformat() if observed_at else None,
                "future_receipt_ignored": status == "waiting"
                and received is not None
                and received > as_of,
                "future_cancel_ignored": status != "cancelled"
                and cancelled is not None
                and cancelled > as_of,
            }
        )
    return rows


_STATUS_RANK = {"completed": 0, "waiting": 1, "cancelled": 2}


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            _STATUS_RANK.get(row["status"], 9),
            row["wait_days"],
            str(row["order_id"]),
        ),
    )
