from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

from app.providers.base import PriceProvider

FIXTURE_DIR = Path(__file__).resolve().parents[4] / "data" / "fixtures"

BUILTIN_COMMODITIES: dict[str, dict] = {
    "lithium_carbonate": {
        "benchmark": "Lithium Carbonate (China)",
        "currency": "CNY",
        "unit": "tonne",
        "base_price": 97500,
        "volatility": 0.02,
    },
    "copper": {
        "benchmark": "LME Copper Official",
        "currency": "USD",
        "unit": "tonne",
        "base_price": 9850,
        "volatility": 0.01,
    },
    "iron_ore": {
        "benchmark": "62% Fe CFR China",
        "currency": "USD",
        "unit": "tonne",
        "base_price": 108,
        "volatility": 0.015,
    },
}


class CsvFixtureProvider(PriceProvider):
    name = "fixture"

    def __init__(self) -> None:
        self._csv_data: dict[str, list[dict]] = {}
        self._load_csv()

    def _load_csv(self) -> None:
        csv_path = FIXTURE_DIR / "prices.csv"
        if not csv_path.exists():
            return
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                commodity = row.get("commodity", "").strip()
                if commodity:
                    self._csv_data.setdefault(commodity, []).append(row)

    def supports(self, commodity: str) -> bool:
        return commodity in BUILTIN_COMMODITIES or commodity in self._csv_data

    def _generate_price(self, commodity: str, dt: date) -> dict | None:
        spec = BUILTIN_COMMODITIES.get(commodity)
        if not spec:
            return None
        seed = hash((commodity, dt.isoformat()))
        rng = random.Random(seed)
        days_offset = (date.today() - dt).days
        drift = -0.001 * days_offset
        noise = rng.gauss(0, spec["volatility"])
        factor = 1.0 + drift + noise
        price = round(spec["base_price"] * factor, 2)
        return {
            "commodity": commodity,
            "benchmark": spec["benchmark"],
            "date": dt.isoformat(),
            "price": price,
            "currency": spec["currency"],
            "unit": spec["unit"],
            "price_type": "official_close",
            "source": "fixture",
            "is_delayed": False,
            "is_demo": True,
            "warnings": ["Demo fixture data is being used."],
        }

    async def get_price(self, commodity: str, dt: date, benchmark: str | None = None) -> dict | None:
        if commodity in self._csv_data:
            target = dt.isoformat()
            for row in self._csv_data[commodity]:
                if row.get("date") == target:
                    return {
                        "commodity": commodity,
                        "benchmark": row.get("benchmark", benchmark or commodity),
                        "date": target,
                        "price": float(row["price"]),
                        "currency": row.get("currency", "USD"),
                        "unit": row.get("unit", "tonne"),
                        "price_type": "official_close",
                        "source": "fixture",
                        "is_delayed": False,
                        "is_demo": True,
                        "warnings": ["Demo fixture data is being used."],
                    }
            closest = min(self._csv_data[commodity], key=lambda r: abs((date.fromisoformat(r["date"]) - dt).days))
            return {
                "commodity": commodity,
                "benchmark": closest.get("benchmark", benchmark or commodity),
                "date": closest["date"],
                "price": float(closest["price"]),
                "currency": closest.get("currency", "USD"),
                "unit": closest.get("unit", "tonne"),
                "price_type": "official_close",
                "source": "fixture",
                "is_delayed": False,
                "is_demo": True,
                "warnings": ["Demo fixture data is being used.", f"Closest available date: {closest['date']}"],
            }
        return self._generate_price(commodity, dt)

    async def get_trend(self, commodity: str, days: int, benchmark: str | None = None) -> dict | None:
        today = date.today()
        points = []
        for i in range(days, -1, -1):
            dt = today - timedelta(days=i)
            result = await self.get_price(commodity, dt, benchmark)
            if result:
                points.append({"date": result["date"], "price": result["price"]})

        if len(points) < 2:
            return None

        prices = [p["price"] for p in points]
        start_price = prices[0]
        end_price = prices[-1]
        change = round(end_price - start_price, 2)
        change_pct = round((change / start_price) * 100, 2) if start_price else 0

        spec = BUILTIN_COMMODITIES.get(commodity, {})
        return {
            "commodity": commodity,
            "benchmark": spec.get("benchmark", benchmark or commodity),
            "period": {
                "start": points[0]["date"],
                "end": points[-1]["date"],
                "days": days,
            },
            "start_price": start_price,
            "end_price": end_price,
            "change": change,
            "change_percent": change_pct,
            "min_price": min(prices),
            "max_price": max(prices),
            "currency": spec.get("currency", "USD"),
            "unit": spec.get("unit", "tonne"),
            "points": points,
            "source": "fixture",
            "is_demo": True,
            "warnings": ["Demo fixture data is being used."],
        }