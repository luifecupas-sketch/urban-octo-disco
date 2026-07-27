"""Orchestrator: check every configured retailer, apply coupons, record
history, write a human-readable report, and email a daily digest.

Usage:
    python -m deal_finder.main [--no-email]

Designed to be run daily from .github/workflows/deal-search.yml, but works
fine locally too (useful for testing after changing retailers.yaml).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import notifier, state
from .pricing import PricedDeal, price_deals
from .scraper import fetch_price

REPO_ROOT = Path(__file__).resolve().parents[2]
RETAILERS_CONFIG = REPO_ROOT / "config" / "retailers.yaml"
COUPONS_CONFIG = REPO_ROOT / "config" / "coupons.json"
HISTORY_FILE = REPO_ROOT / "data" / "price_history.json"
REPORT_FILE = REPO_ROOT / "reports" / "latest_deals.md"


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(path: Path) -> dict:
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def format_report(product_name: str, deals: list[PricedDeal], failures: list[tuple[str, str]], new_low: bool, previous_low) -> str:
    lines = [f"# {product_name} - deal report", ""]

    if deals:
        best = deals[0]
        lines.append(f"**Best deal found: ${best.effective_price:.2f} at {best.retailer}**")
        if best.applied_coupon:
            lines.append(f"(after coupon `{best.applied_coupon}`, list price was ${best.list_price:.2f})")
        if new_low:
            prev = f"${previous_low:.2f}" if previous_low is not None else "n/a"
            lines.append(f"\n:tada: This is a new all-time low in our tracked history (previous: {prev}).")
        lines.append("")
        lines.append("| Retailer | List price | Effective price | Coupon | In stock |")
        lines.append("|---|---|---|---|---|")
        for d in deals:
            coupon = d.applied_coupon or "-"
            stock = "yes" if d.in_stock else ("no" if d.in_stock is False else "unknown")
            lines.append(
                f"| [{d.retailer}]({d.url}) | ${d.list_price:.2f} | ${d.effective_price:.2f} | {coupon} | {stock} |"
            )
    else:
        lines.append("No prices could be retrieved this run - every retailer failed. See errors below.")

    if failures:
        lines.append("")
        lines.append("## Retailers that could not be checked this run")
        lines.append("")
        for retailer, error in failures:
            lines.append(f"- **{retailer}**: {error}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="skip sending the email digest")
    args = parser.parse_args()

    config = load_yaml(RETAILERS_CONFIG)
    coupons = load_json(COUPONS_CONFIG).get("codes", [])
    product_name = config["product"]["name"]

    results = []
    failures: list[tuple[str, str]] = []
    for retailer in config["retailers"]:
        result = fetch_price(retailer["name"], retailer["url"], retailer.get("parser", "jsonld"))
        if result.error:
            failures.append((retailer["name"], result.error))
        else:
            results.append(result)

    deals = price_deals(results, coupons)

    history = state.load_history(HISTORY_FILE)
    previous_low = state.all_time_low(history)
    state.record_run(HISTORY_FILE, history, deals)

    new_low = bool(deals) and (previous_low is None or deals[0].effective_price < previous_low)

    report = format_report(product_name, deals, failures, new_low, previous_low)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report)

    if args.no_email:
        print("(--no-email passed, skipping email digest)")
        return 0

    subject = f"{product_name} deal digest"
    if deals:
        subject += f" - best: ${deals[0].effective_price:.2f} at {deals[0].retailer}"
        if new_low:
            subject += " (new low!)"

    try:
        notifier.send_digest(subject, report)
    except notifier.EmailConfigError as exc:
        print(f"Email not sent: {exc}", file=sys.stderr)
        # Not a hard failure: the report file/history were still updated.
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
