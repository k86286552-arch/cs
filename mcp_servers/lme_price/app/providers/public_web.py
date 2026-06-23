from __future__ import annotations

import html
import json
import os
import re
from datetime import date, datetime, timedelta

import httpx

from app.providers.base import PriceProvider

PAGE_CONFIG: dict[str, dict[str, str]] = {
    "copper": {
        "url": "https://tradingeconomics.com/commodity/copper",
        "benchmark": "Copper",
    },
    "nickel": {
        "url": "https://tradingeconomics.com/commodity/nickel",
        "benchmark": "Nickel",
    },
    "zinc": {
        "url": "https://tradingeconomics.com/commodity/zinc",
        "benchmark": "Zinc",
    },
    "lithium_carbonate": {
        "url": "https://tradingeconomics.com/commodity/lithium",
        "benchmark": "Lithium Carbonate",
    },
    "iron_ore": {
        "url": "https://tradingeconomics.com/commodity/iron-ore-cny",
        "benchmark": "Iron Ore CNY",
    },
}

META_DESC_RE = re.compile(r'<meta[^>]+id="metaDesc"[^>]+content="([^"]+)"', re.IGNORECASE)
CHARTS_META_RE = re.compile(r"TEChartsMeta = (\[.*?\]);", re.DOTALL)
CURRENT_RE = re.compile(
    r"(?P<name>[A-Za-z ]+?)\s+(?:rose|fell)\s+to\s+"
    r"(?P<price>[\d,]+(?:\.\d+)?)\s+"
    r"(?P<currency>[A-Z]{3})/(?P<unit>[A-Za-z]+)\s+on\s+"
    r"(?P<as_of>[A-Za-z]+\s+\d{1,2},\s+\d{4}),\s+"
    r"(?P<daily_direction>up|down)\s+(?P<daily_change>[\d.]+)%",
    re.IGNORECASE,
)
MONTH_CHANGE_RE = re.compile(
    r"Over the past month, .*? price has "
    r"(?P<direction>fallen|risen|rose|increased|decreased)\s+"
    r"(?P<pct>[\d.]+)%",
    re.IGNORECASE,
)
YEAR_CHANGE_RE = re.compile(
    r"it is still\s+(?P<pct>[\d.]+)%\s+"
    r"(?P<direction>higher|lower)\s+than a year ago",
    re.IGNORECASE,
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _env_enabled(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _signed_percent(direction: str, value: str) -> float:
    pct = float(value)
    return -pct if direction.lower() in {"fell", "fallen", "decreased", "lower", "down"} else pct


def _normalize_unit(unit: str) -> str:
    normalized = unit.strip().lower()
    if normalized == "t":
        return "tonne"
    if normalized == "lbs":
        return "lb"
    return normalized


class TradingEconomicsWebProvider(PriceProvider):
    name = "public_web"

    def __init__(self) -> None:
        self.enabled = _env_enabled("PRICE_PUBLIC_WEB_ENABLED", default=True)
        self.timeout_seconds = float(os.environ.get("PRICE_PUBLIC_WEB_TIMEOUT_SECONDS", "30"))

    def is_configured(self) -> bool:
        return self.enabled

    def supports(self, commodity: str) -> bool:
        return commodity in PAGE_CONFIG

    async def _fetch_page(self, commodity: str) -> str:
        cfg = PAGE_CONFIG[commodity]
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=self.timeout_seconds, headers=headers, follow_redirects=True) as client:
            response = await client.get(cfg["url"])
            response.raise_for_status()
            return response.text

    def _extract_meta_description(self, html_text: str) -> str | None:
        match = META_DESC_RE.search(html_text)
        if not match:
            return None
        return html.unescape(match.group(1))

    def _extract_benchmark(self, html_text: str, commodity: str, fallback_benchmark: str | None) -> str:
        match = CHARTS_META_RE.search(html_text)
        if match:
            try:
                payload = json.loads(match.group(1))
                if payload and payload[0].get("full_name"):
                    return str(payload[0]["full_name"])
            except json.JSONDecodeError:
                pass
        return fallback_benchmark or PAGE_CONFIG[commodity]["benchmark"]

    def _parse_current_snapshot(self, meta_desc: str) -> dict | None:
        match = CURRENT_RE.search(meta_desc)
        if not match:
            return None

        snapshot_date = datetime.strptime(match.group("as_of"), "%B %d, %Y").date()
        return {
            "date": snapshot_date,
            "price": float(match.group("price").replace(",", "")),
            "currency": match.group("currency"),
            "unit": _normalize_unit(match.group("unit")),
            "daily_change_percent": _signed_percent(match.group("daily_direction"), match.group("daily_change")),
        }

    def _parse_summary_change(self, meta_desc: str, days: int) -> tuple[float, str] | None:
        if days <= 45:
            month_match = MONTH_CHANGE_RE.search(meta_desc)
            if month_match:
                base_pct = _signed_percent(month_match.group("direction"), month_match.group("pct"))
                scale = days / 30
                return base_pct * scale, "public 30-day summary"

        year_match = YEAR_CHANGE_RE.search(meta_desc)
        if year_match:
            base_pct = _signed_percent(year_match.group("direction"), year_match.group("pct"))
            scale = days / 365
            return base_pct * scale, "public 1-year summary"

        month_match = MONTH_CHANGE_RE.search(meta_desc)
        if month_match:
            base_pct = _signed_percent(month_match.group("direction"), month_match.group("pct"))
            scale = days / 30
            return base_pct * scale, "public 30-day summary"

        return None

    async def get_price(self, commodity: str, dt: date, benchmark: str | None = None) -> dict | None:
        if not self.enabled or not self.supports(commodity):
            return None

        html_text = await self._fetch_page(commodity)
        meta_desc = self._extract_meta_description(html_text)
        if not meta_desc:
            return None

        current = self._parse_current_snapshot(meta_desc)
        if not current:
            return None

        warnings = [
            "Price was parsed from a public commodity webpage rather than a direct exchange/API feed.",
        ]
        if current["date"] != dt:
            warnings.append(f"Latest available public page date: {current['date'].isoformat()}.")

        return {
            "commodity": commodity,
            "benchmark": self._extract_benchmark(html_text, commodity, benchmark),
            "date": current["date"].isoformat(),
            "price": current["price"],
            "currency": current["currency"],
            "unit": current["unit"],
            "price_type": "public_page_latest",
            "source": "tradingeconomics-public-web",
            "source_url": PAGE_CONFIG[commodity]["url"],
            "is_delayed": False,
            "is_demo": False,
            "warnings": warnings,
        }

    async def get_trend(self, commodity: str, days: int, benchmark: str | None = None) -> dict | None:
        if not self.enabled or not self.supports(commodity):
            return None

        html_text = await self._fetch_page(commodity)
        meta_desc = self._extract_meta_description(html_text)
        if not meta_desc:
            return None

        current = self._parse_current_snapshot(meta_desc)
        if not current:
            return None

        parsed_change = self._parse_summary_change(meta_desc, days)
        if not parsed_change:
            return None

        change_percent, basis = parsed_change
        denominator = 1 + (change_percent / 100)
        if denominator == 0:
            return None

        end_price = current["price"]
        start_price = round(end_price / denominator, 2)
        end_date = current["date"]
        start_date = end_date - timedelta(days=days)
        change = round(end_price - start_price, 2)
        effective_change_pct = round(((change / start_price) * 100), 2) if start_price else 0.0

        warnings = [
            (
                f"Trend was reconstructed from {basis}; it is not a full historical time series "
                f"from a direct market data API."
            ),
            "Only start/end points are available for this public-web trend reconstruction.",
        ]

        return {
            "commodity": commodity,
            "benchmark": self._extract_benchmark(html_text, commodity, benchmark),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "start_price": start_price,
            "end_price": end_price,
            "change": change,
            "change_percent": effective_change_pct,
            "min_price": min(start_price, end_price),
            "max_price": max(start_price, end_price),
            "currency": current["currency"],
            "unit": current["unit"],
            "points": [
                {"date": start_date.isoformat(), "price": start_price},
                {"date": end_date.isoformat(), "price": end_price},
            ],
            "source": "tradingeconomics-public-web",
            "source_url": PAGE_CONFIG[commodity]["url"],
            "is_demo": False,
            "is_estimated": True,
            "warnings": warnings,
        }
