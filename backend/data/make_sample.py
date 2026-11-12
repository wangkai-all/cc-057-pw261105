"""Sample order book covering every state the page must explain.

Design intent (dates are absolute so tests can pin behaviour):

* A–E   completed orders with short/medium waits, all received before the
        default cut-off of 2026-06-30.
* F–J   still waiting at the cut-off: the right-censored tail.
* K–L   same-day receipt AND censoring at day 12 — K receives on 06-12
        (counted in the event step) while L is a waiting order that has
        also reached exactly 12 days at the cut-off.  This pins the
        "events first, censoring second" rule.
* M–O   long delivery waits (60–90 days) that pull the tail down and let
        the 90th percentile become estimable in the full sample.
* P–Q   very long receipts (140 days) that take survival below 10%; the
        full sample can report a 90th percentile while narrow supplier
        filters cannot.
* P–R   cancelled before the cut-off — excluded from the curve.
* S–T   the cut-off flips: S receives AFTER the cut-off (must stay waiting
        at 06-30, then become completed at 07-31); T is cancelled after
        the cut-off (must stay in the curve at 06-30, then drop out at
        07-31 and join the cancelled list).
* U–V   completed right at the cut-off boundary (receipt == as_of counts
        as completed; a receipt one day later does not).
* W–Z   small suppliers/materials so filters visibly change the cohort.
* K-*   an all-waiting supplier: no receipt at any cut-off, so its curve
        stays flat at 100% and its median is unestimable.
* L-*   an all-completed supplier: every order received, so the curve
        reaches 0% and the completed-mean tile has a clean cohort.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROWS = [
    # order_id, supplier, material, order_date, full_receipt_date, cancel_date
    ("A-1001", "华东精密", "轴承", "2026-01-05", "2026-01-19", ""),
    ("A-1002", "华东精密", "轴承", "2026-01-10", "2026-01-31", ""),
    ("A-1003", "华东精密", "密封件", "2026-02-02", "2026-02-20", ""),
    ("A-1004", "华东精密", "轴承", "2026-02-15", "2026-03-12", ""),
    ("A-1005", "华东精密", "密封件", "2026-03-01", "2026-03-25", ""),
    # waiting at 2026-06-30
    ("B-2001", "华南机电", "电机", "2026-02-01", "", ""),
    ("B-2002", "华南机电", "电机", "2026-03-15", "", ""),
    ("B-2003", "华南机电", "电控", "2026-04-10", "", ""),
    ("B-2004", "华南机电", "电机", "2026-05-20", "", ""),
    ("B-2005", "华南机电", "电控", "2026-06-10", "", ""),
    # same-day receipt + censoring at day 12
    ("C-3001", "北方重工", "液压件", "2026-02-01", "2026-02-13", ""),  # day 12 event
    ("C-3002", "北方重工", "液压件", "2026-06-18", "", ""),  # day 12 censored at 06-30
    # long waits
    ("D-4001", "北方重工", "液压件", "2026-01-20", "2026-04-20", ""),  # 90 days
    ("D-4002", "北方重工", "阀体", "2026-02-10", "2026-05-11", ""),  # 90 days
    ("D-4003", "华东精密", "轴承", "2026-03-10", "2026-06-08", ""),  # 90 days
    # very long receipts that pull S below 10%
    ("D-4004", "北方重工", "阀体", "2026-01-10", "2026-05-30", ""),  # 140 days
    ("D-4005", "华东精密", "密封件", "2026-02-01", "2026-06-21", ""),  # 140 days
    # cancelled before the default cut-off
    ("E-5001", "西部仪表", "传感器", "2026-01-15", "", "2026-02-14"),
    ("E-5002", "西部仪表", "传感器", "2026-03-20", "", "2026-04-09"),
    ("E-5003", "西部仪表", "传感器", "2026-05-01", "", "2026-06-15"),
    # cut-off flips between 2026-06-30 and 2026-07-31
    ("F-6001", "西部仪表", "传感器", "2026-03-01", "2026-07-10", ""),  # receipt after 06-30
    ("F-6002", "西部仪表", "传感器", "2026-04-01", "", "2026-07-20"),  # cancelled after 06-30
    # boundary receipt at the cut-off
    ("G-7001", "华南机电", "电控", "2026-03-01", "2026-06-30", ""),  # 121 days, event at as_of
    ("G-7002", "华南机电", "电控", "2026-04-30", "2026-07-01", ""),  # one day after 06-30
    # filter-cohort variety
    ("H-8001", "小型供应商", "紧固件", "2026-04-01", "2026-04-16", ""),
    ("H-8002", "小型供应商", "紧固件", "2026-05-01", "", ""),
    ("H-8003", "小型供应商", "紧固件", "2026-05-25", "2026-06-20", ""),
    ("H-8004", "小型供应商", "紧固件", "2026-06-01", "", ""),
    ("H-8005", "华东精密", "紧固件", "2026-05-10", "2026-05-30", ""),
    # all-waiting cohort: curve stays flat, median unestimable
    ("K-9001", "全线待收", "标准件", "2026-01-20", "", ""),
    ("K-9002", "全线待收", "标准件", "2026-03-05", "", ""),
    ("K-9003", "全线待收", "标准件", "2026-05-15", "", ""),
    # all-completed cohort: curve reaches 0%, no censoring
    ("L-9101", "全部收货", "标准件", "2026-01-12", "2026-01-26", ""),
    ("L-9102", "全部收货", "标准件", "2026-02-08", "2026-03-02", ""),
    ("L-9103", "全部收货", "标准件", "2026-04-03", "2026-04-24", ""),
]

HEADER = (
    "order_id",
    "supplier",
    "material",
    "order_date",
    "full_receipt_date",
    "cancel_date",
)


def write(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(ROWS)


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "orders.csv"
    write(target)
    print(f"wrote {len(ROWS)} orders to {target}")
