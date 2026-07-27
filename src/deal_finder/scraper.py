"""Best-effort price scraping for a fixed list of retailer product pages.

Most large retailers run bot-detection (Akamai, PerimeterX, Cloudflare, ...)
that can block plain HTTP requests, especially from datacenter IPs such as
GitHub Actions runners. This module does not try to defeat that - it sends
normal browser-like headers, parses whatever HTML comes back, and reports a
clean failure (instead of crashing) when a retailer blocks or restructures
its page. See README.md for what to do about retailers that fail
consistently (e.g. Amazon).
"""
from __future__ import annotations

import dataclasses
import json
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT_SECONDS = 20


@dataclasses.dataclass
class PriceResult:
    retailer: str
    url: str
    price: Optional[float]
    currency: str = "USD"
    in_stock: Optional[bool] = None
    error: Optional[str] = None


def _find_jsonld_price(soup: BeautifulSoup) -> tuple[Optional[float], Optional[bool]]:
    """Look for schema.org Product/Offer JSON-LD and pull out price + availability."""
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue

            item_type = item.get("@type")
            type_names = item_type if isinstance(item_type, list) else [item_type]
            if "Product" not in type_names:
                # Some sites nest the Product under @graph
                graph = item.get("@graph")
                if isinstance(graph, list):
                    candidates.extend(g for g in graph if isinstance(g, dict))
                continue

            offers = item.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if not isinstance(offers, dict):
                continue

            price = offers.get("price") or offers.get("lowPrice")
            if price is None:
                continue
            try:
                price_val = float(str(price).replace(",", ""))
            except ValueError:
                continue

            availability = offers.get("availability", "")
            in_stock = None
            if isinstance(availability, str):
                in_stock = "InStock" in availability

            return price_val, in_stock

    return None, None


def _find_regex_price(html: str) -> Optional[float]:
    """Last-resort fallback: first $XXX.XX-looking price near the top of the page."""
    match = re.search(r"\$\s?(\d{2,4}(?:\.\d{2})?)", html)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def fetch_price(retailer: str, url: str, parser: str = "jsonld") -> PriceResult:
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        return PriceResult(retailer=retailer, url=url, price=None, error=f"request failed: {exc}")

    if response.status_code != 200:
        return PriceResult(
            retailer=retailer,
            url=url,
            price=None,
            error=f"HTTP {response.status_code} (likely blocked or page moved)",
        )

    soup = BeautifulSoup(response.text, "lxml")

    price: Optional[float] = None
    in_stock: Optional[bool] = None

    if parser == "jsonld":
        price, in_stock = _find_jsonld_price(soup)

    if price is None:
        price = _find_regex_price(response.text)

    if price is None:
        return PriceResult(
            retailer=retailer,
            url=url,
            price=None,
            error="could not find a price on the page (layout changed or blocked)",
        )

    return PriceResult(retailer=retailer, url=url, price=price, in_stock=in_stock)
