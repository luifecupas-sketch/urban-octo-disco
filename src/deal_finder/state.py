"""Persist price history to a JSON file so we can tell when today's best
price is a new all-time low."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .pricing import PricedDeal


def load_history(path: Path) -> dict:
    if not path.exists():
        return {"runs": []}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def all_time_low(history: dict) -> Optional[float]:
    prices = [
        deal["effective_price"]
        for run in history.get("runs", [])
        for deal in run.get("deals", [])
    ]
    return min(prices) if prices else None


def record_run(path: Path, history: dict, deals: list[PricedDeal]) -> dict:
    run = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "deals": [
            {
                "retailer": d.retailer,
                "list_price": d.list_price,
                "effective_price": d.effective_price,
                "applied_coupon": d.applied_coupon,
                "in_stock": d.in_stock,
            }
            for d in deals
        ],
    }
    history.setdefault("runs", []).append(run)
    # Keep the file from growing forever - one year of daily runs is plenty.
    history["runs"] = history["runs"][-365:]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
        f.write("\n")

    return run
