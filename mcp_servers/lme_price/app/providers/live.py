from __future__ import annotations

import os
from datetime import date

import httpx

from app.providers.base import PriceProvider
from app.providers.public_web import TradingEconomicsWebProvider

SUPPORTED_COMMODITIES = {
    "copper",
    "nickel",
    "zinc",
    "lithium_carbonate",
    "iron_ore",
}


class HttpApiPriceProvider(PriceProvider):
    name = "live_api"

    def __init__(self) -> None:
        self.base_url = os.environ.get("PRICE_LIVE_BASE_URL", "").strip().rstrip("/")
        self.api_key = os.environ.get("PRICE_LIVE_API_KEY", "").strip()
        self.timeout_seconds = float(os.environ.get("PRICE_LIVE_TIMEOUT_SECONDS", "30"))

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def supports(self, commodity: str) -> bool:
        return commodity in SUPPORTED_COMMODITIES

    async def get_price(self, commodity: str, dt: date, benchmark: str | None = None) -> dict | None:
        if not self.is_configured():
            return None

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/price",
                params={"commodity": commodity, "date": dt.isoformat(), "benchmark": benchmark or ""},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            payload = response.json()

        payload.setdefault("source", "live")
        payload.setdefault("is_demo", False)
        return payload

    async def get_trend(self, commodity: str, days: int, benchmark: str | None = None) -> dict | None:
        if not self.is_configured():
            return None

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                f"{self.base_url}/trend",
                params={"commodity": commodity, "days": days, "benchmark": benchmark or ""},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            payload = response.json()

        payload.setdefault("source", "live")
        payload.setdefault("is_demo", False)
        return payload


class LivePriceProvider(PriceProvider):
    name = "live"

    def __init__(self) -> None:
        self.providers: list[PriceProvider] = [
            HttpApiPriceProvider(),
            TradingEconomicsWebProvider(),
        ]

    def is_configured(self) -> bool:
        return any(provider.is_configured() for provider in self.providers)

    def supports(self, commodity: str) -> bool:
        return any(provider.supports(commodity) for provider in self.providers)

    async def get_price(self, commodity: str, dt: date, benchmark: str | None = None) -> dict | None:
        for provider in self.providers:
            if not provider.is_configured() or not provider.supports(commodity):
                continue
            try:
                result = await provider.get_price(commodity, dt, benchmark)
            except Exception:
                continue
            if result is not None:
                return result
        return None

    async def get_trend(self, commodity: str, days: int, benchmark: str | None = None) -> dict | None:
        for provider in self.providers:
            if not provider.is_configured() or not provider.supports(commodity):
                continue
            try:
                result = await provider.get_trend(commodity, days, benchmark)
            except Exception:
                continue
            if result is not None:
                return result
        return None
