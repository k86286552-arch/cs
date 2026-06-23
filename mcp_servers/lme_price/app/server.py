from __future__ import annotations

import logging
import os
import sys
from datetime import date

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from app.providers.fixture import CsvFixtureProvider
from app.providers.live import LivePriceProvider

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("lme-price-mcp")

mcp = FastMCP("lme-price-mcp")


def _get_data_mode() -> str:
    explicit = os.environ.get("PRICE_DATA_MODE", "").strip().lower()
    if explicit in {"live", "fixture"}:
        return explicit

    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    return "fixture" if app_env == "development" else "live"


def _get_provider():
    return LivePriceProvider() if _get_data_mode() == "live" else CsvFixtureProvider()


provider = _get_provider()


class GetPriceArgs(BaseModel):
    commodity: str = Field(description="Commodity identifier, e.g. 'copper', 'lithium_carbonate', 'iron_ore'")
    date: str = Field(description="Date in ISO format, e.g. '2026-06-22'")
    benchmark: str | None = Field(default=None, description="Optional benchmark name override")


class GetTrendArgs(BaseModel):
    commodity: str = Field(description="Commodity identifier")
    days: int = Field(default=30, ge=2, le=365, description="Number of days for trend analysis")
    benchmark: str | None = Field(default=None, description="Optional benchmark name override")


@mcp.tool()
async def get_price(commodity: str, date: str, benchmark: str | None = None) -> dict:
    """Get the price for a commodity on a specific date.

    Returns price, currency, unit, source, and data quality flags.
    """
    logger.info("get_price called: commodity=%s date=%s", commodity, date)

    if _get_data_mode() == "live" and not provider.is_configured():
        return {
            "error_code": "PRICE_PROVIDER_UNAVAILABLE",
            "message": (
                "Live price mode is enabled, but no live provider is configured. "
                "Set PRICE_LIVE_BASE_URL and PRICE_LIVE_API_KEY, enable PRICE_PUBLIC_WEB_ENABLED=1, "
                "or switch PRICE_DATA_MODE=fixture."
            ),
            "retryable": False,
            "component": "price",
        }

    if not provider.supports(commodity):
        return {
            "error_code": "UNSUPPORTED_COMMODITY",
            "message": f"Commodity '{commodity}' is not supported.",
            "retryable": False,
            "component": "price",
        }

    try:
        dt = __import__("datetime").date.fromisoformat(date)
    except ValueError:
        return {
            "error_code": "INVALID_ARGUMENT",
            "message": f"Invalid date format: '{date}'. Use YYYY-MM-DD.",
            "retryable": False,
            "component": "price",
        }

    result = await provider.get_price(commodity, dt, benchmark)
    if result is None:
        return {
            "error_code": "PRICE_NOT_FOUND",
            "message": f"No price found for {commodity} on {date}.",
            "retryable": False,
            "component": "price",
        }
    return result


@mcp.tool()
async def get_trend(commodity: str, days: int = 30, benchmark: str | None = None) -> dict:
    """Get the price trend for a commodity over the specified number of days.

    Returns start/end prices, change percentage, min/max, and data points.
    """
    logger.info("get_trend called: commodity=%s days=%d", commodity, days)

    if _get_data_mode() == "live" and not provider.is_configured():
        return {
            "error_code": "PRICE_PROVIDER_UNAVAILABLE",
            "message": (
                "Live price mode is enabled, but no live provider is configured. "
                "Set PRICE_LIVE_BASE_URL and PRICE_LIVE_API_KEY, enable PRICE_PUBLIC_WEB_ENABLED=1, "
                "or switch PRICE_DATA_MODE=fixture."
            ),
            "retryable": False,
            "component": "price",
        }

    if not provider.supports(commodity):
        return {
            "error_code": "UNSUPPORTED_COMMODITY",
            "message": f"Commodity '{commodity}' is not supported.",
            "retryable": False,
            "component": "price",
        }

    if days < 2 or days > 365:
        return {
            "error_code": "INVALID_ARGUMENT",
            "message": "days must be between 2 and 365.",
            "retryable": False,
            "component": "price",
        }

    result = await provider.get_trend(commodity, days, benchmark)
    if result is None:
        return {
            "error_code": "PRICE_PROVIDER_UNAVAILABLE",
            "message": "Could not generate trend data.",
            "retryable": True,
            "component": "price",
        }
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
