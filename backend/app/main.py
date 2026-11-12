"""FastAPI surface for the delivery-time survival analysis."""

from __future__ import annotations

import threading
from datetime import date
from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .analysis import analyse
from .data import (
    ORDERS_CSV,
    book_bounds,
    connect,
    cutoff_presets,
    load_csv,
    load_orders,
    materials,
    suppliers,
)
from .model import ValidationError, parse_date

app = FastAPI(title="交期分析 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_con: duckdb.DuckDBPyConnection | None = None
_lock = threading.RLock()


def get_con() -> duckdb.DuckDBPyConnection:
    """Shared in-memory database.

    Sync FastAPI endpoints run in a thread pool; DuckDB connections are not
    thread-safe, so each request gets its own cursor and mutations are
    serialised by the lock.
    """
    global _con
    with _lock:
        if _con is None:
            _con = connect()
        return _con


def request_con() -> duckdb.DuckDBPyConnection:
    return get_con().cursor()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _bounds(con: duckdb.DuckDBPyConnection) -> tuple[date, date]:
    return book_bounds(con)


@app.get("/api/filters")
def filters() -> dict:
    con = request_con()
    first, last = _bounds(con)
    return {
        "suppliers": suppliers(con),
        "materials": materials(con),
        "min_cutoff": first.isoformat(),
        "max_cutoff": last.isoformat(),
        "default_cutoff": last.isoformat(),
        "cutoff_presets": cutoff_presets(con),
    }


@app.get("/api/analysis")
def analysis(
    as_of: str | None = Query(None, description="统计截止日 YYYY-MM-DD"),
    supplier: str | None = Query(None),
    material: str | None = Query(None),
) -> dict:
    con = request_con()
    first, last = _bounds(con)
    try:
        cutoff = parse_date(as_of) or last
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"截至日格式无效: {as_of}") from exc

    if cutoff < first:
        raise HTTPException(
            status_code=422,
            detail=f"截止日不能早于首笔下单日 {first.isoformat()}",
        )
    orders = load_orders(con, supplier=supplier, material=material)
    try:
        payload = analyse(orders, cutoff)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload["filters"] = {"supplier": supplier, "material": material}
    return payload


@app.get("/api/orders/{order_id}")
def order_detail(order_id: str) -> dict:
    con = request_con()
    rows = load_orders(con)
    for order in rows:
        if str(order["order_id"]) == order_id:
            return order
    raise HTTPException(status_code=404, detail="订单不存在")


@app.post("/api/reload")
def reload_data(csv_path: str | None = None) -> dict[str, str]:
    """Reload the order book (used by tests and data swaps)."""
    path = Path(csv_path) if csv_path else ORDERS_CSV
    with _lock:
        con = get_con()
        load_csv(con, path)
        first, last = _bounds(con)
    return {"loaded": str(path), "min_cutoff": first.isoformat(), "max_cutoff": last.isoformat()}
