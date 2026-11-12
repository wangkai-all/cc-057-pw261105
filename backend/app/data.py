"""Data layer: a small DuckDB store plus the as-of query.

The sample data ships as CSV.  SQL keeps the "restore the state at the cut-off"
rule in one place: events dated after the cut-off simply do not join.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import duckdb

from .model import ValidationError

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORDERS_CSV = DATA_DIR / "orders.csv"

COLUMNS = (
    "order_id",
    "supplier",
    "material",
    "order_date",
    "full_receipt_date",
    "cancel_date",
)


def connect(csv_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """In-process DuckDB with the sample order book loaded into ``orders``."""
    con = duckdb.connect(database=":memory:")
    load_csv(con, csv_path or ORDERS_CSV)
    return con


def load_csv(con: duckdb.DuckDBPyConnection, csv_path: Path) -> None:
    if not csv_path.exists():
        raise FileNotFoundError(f"order book not found: {csv_path}")
    con.execute("DROP TABLE IF EXISTS orders")
    con.execute(
        """
        CREATE TABLE orders (
            order_id          VARCHAR PRIMARY KEY,
            supplier          VARCHAR NOT NULL,
            material          VARCHAR NOT NULL,
            order_date        DATE NOT NULL,
            full_receipt_date DATE,
            cancel_date       DATE
        )
        """
    )
    # Read as raw text first so empty strings become NULL rather than parse errors.
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValidationError(f"{csv_path.name} missing columns: {sorted(missing)}")
        flat = [[row[c] or None for c in COLUMNS] for row in reader]
    con.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", flat)
    validate_book(con)


def validate_book(con: duckdb.DuckDBPyConnection) -> None:
    rows = load_orders(con)
    for order in rows:
        ordered = order["order_date"]
        received = order["full_receipt_date"]
        cancelled = order["cancel_date"]
        if received is not None and received < ordered:
            raise ValidationError(
                f"order {order['order_id']}: received before ordered"
            )
        if cancelled is not None and cancelled < ordered:
            raise ValidationError(
                f"order {order['order_id']}: cancelled before ordered"
            )
        if received is not None and cancelled is not None:
            raise ValidationError(
                f"order {order['order_id']}: both full receipt and cancellation set"
            )


def suppliers(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT supplier FROM orders ORDER BY 1"
        ).fetchall()
    ]


def materials(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT material FROM orders ORDER BY 1"
        ).fetchall()
    ]


def load_orders(
    con: duckdb.DuckDBPyConnection,
    *,
    supplier: str | None = None,
    material: str | None = None,
) -> list[dict]:
    """Return orders matching the dimension filters, dates as Python dates.

    No cut-off logic here: the as-of rule lives in ``model.status_at`` so it
    stays testable and identical for every caller.
    """
    where: list[str] = []
    params: list[object] = []
    if supplier is not None:
        where.append("supplier = ?")
        params.append(supplier)
    if material is not None:
        where.append("material = ?")
        params.append(material)
    sql = "SELECT * FROM orders"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY order_date, order_id"
    cursor = con.execute(sql, params)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def book_bounds(
    con: duckdb.DuckDBPyConnection,
) -> tuple[date, date]:
    """First order date and last known event date in the (unfiltered) book."""
    row = con.execute(
        """
        SELECT MIN(order_date),
               GREATEST(MAX(order_date),
                        MAX(full_receipt_date),
                        MAX(cancel_date))
        FROM orders
        """
    ).fetchone()
    if row is None or row[0] is None:
        raise ValidationError("order book is empty")
    return row[0], row[1]


def cutoff_presets(
    con: duckdb.DuckDBPyConnection,
) -> list[dict[str, str]]:
    """Cut-off suggestions: month ends plus the data edge.

    Month-end cut-offs are the natural reporting dates; the latest one
    usually sits just before the most recent event, so it also exercises the
    "do not apply future receipts early" rule.
    """
    first, last = book_bounds(con)
    presets: list[dict[str, str]] = [{"date": last.isoformat(), "label": "数据最新"}]
    cursor = date(first.year, first.month, 1)
    while cursor <= last:
        next_month = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
        month_end = next_month - timedelta(days=1)
        if first <= month_end <= last and month_end != last:
            presets.append(
                {
                    "date": month_end.isoformat(),
                    "label": f"{month_end.month} 月末",
                }
            )
        cursor = next_month
    return presets
