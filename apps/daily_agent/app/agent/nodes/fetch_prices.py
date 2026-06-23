from __future__ import annotations

import logging
from datetime import date

from app.agent.state import DailyBriefState

logger = logging.getLogger("daily-agent.fetch_prices")


async def fetch_prices(state: DailyBriefState, mcp_manager) -> dict:
    plan = state.get("plan", {}).get("price", {})
    if not plan.get("enabled") or not plan.get("commodity"):
        return {
            "price_result": None,
            "price_trend": None,
            "tool_status": {**state.get("tool_status", {}), "price": "skipped"},
        }

    commodity = plan["commodity"]
    benchmark = plan.get("benchmark")
    days = plan.get("days", 30)
    today = date.today().isoformat()

    price_result = None
    price_trend = None
    status = "success"

    try:
        price_result = await mcp_manager.call_tool(
            "lme-price-mcp",
            "get_price",
            {"commodity": commodity, "date": today, "benchmark": benchmark},
        )
        if "error_code" in price_result:
            logger.warning("Price fetch error: %s", price_result.get("message"))
            error_code = price_result.get("error_code")
            price_result = None
            status = "unavailable" if error_code == "PRICE_PROVIDER_UNAVAILABLE" else "degraded"
    except Exception as exc:
        logger.error("Price fetch failed: %s", exc)
        status = "error"

    try:
        price_trend = await mcp_manager.call_tool(
            "lme-price-mcp",
            "get_trend",
            {"commodity": commodity, "days": days, "benchmark": benchmark},
        )
        if "error_code" in price_trend:
            logger.warning("Trend fetch error: %s", price_trend.get("message"))
            error_code = price_trend.get("error_code")
            price_trend = None
            if status == "success":
                status = "unavailable" if error_code == "PRICE_PROVIDER_UNAVAILABLE" else "degraded"
    except Exception as exc:
        logger.error("Trend fetch failed: %s", exc)
        if status == "success":
            status = "error"

    warnings: list[dict] = []
    if status == "unavailable":
        warnings.append({
            "component": "price",
            "message": "Live price provider is unavailable or not configured.",
        })

    return {
        "price_result": price_result,
        "price_trend": price_trend,
        "tool_status": {**state.get("tool_status", {}), "price": status},
        "warnings": warnings,
    }
