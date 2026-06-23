from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.agent.state import DailyBriefState

logger = logging.getLogger("daily-agent.risks")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
RISK_RULES_PATH = PROJECT_ROOT / "config" / "risk_rules.yaml"

NEGATIVE_KEYWORDS = {
    "shutdown", "suspension", "accident", "strike", "lawsuit",
    "penalty", "downgrade", "cut", "reduce", "delay", "halt",
    "closure", "bankruptcy", "spill", "contamination",
}


def _load_risk_rules() -> list[dict]:
    if not RISK_RULES_PATH.exists():
        return []
    with open(RISK_RULES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])


async def analyze_risks(state: DailyBriefState) -> dict:
    risks: list[dict] = []
    evidence = state.get("normalized_evidence", [])
    tool_status = state.get("tool_status", {})

    price_trend = state.get("price_trend")
    if price_trend and "error_code" not in price_trend:
        change_pct = price_trend.get("change_percent", 0)
        if change_pct < -5:
            commodity = price_trend.get("commodity", "unknown")
            risks.append({
                "risk_id": "price_drop_significant",
                "severity": "high",
                "description": f"{commodity} price dropped {change_pct:.1f}% over the past {price_trend.get('period', {}).get('days', 30)} days, "
                               f"from {price_trend.get('start_price')} to {price_trend.get('end_price')} "
                               f"{price_trend.get('currency', '')}/{price_trend.get('unit', '')}.",
                "evidence_ids": [e["evidence_id"] for e in evidence if e.get("evidence_type") == "price"],
            })
        elif change_pct > 10:
            risks.append({
                "risk_id": "price_rise_significant",
                "severity": "medium",
                "description": f"{price_trend.get('commodity', '')} price rose {change_pct:.1f}% over the past {price_trend.get('period', {}).get('days', 30)} days.",
                "evidence_ids": [e["evidence_id"] for e in evidence if e.get("evidence_type") == "price"],
            })

    for e in evidence:
        if e.get("evidence_type") == "news":
            text = (e.get("title", "") + " " + e.get("content", "")).lower()
            matched_kw = [kw for kw in NEGATIVE_KEYWORDS if kw in text]
            if matched_kw:
                risks.append({
                    "risk_id": "news_negative_sentiment",
                    "severity": "medium",
                    "description": f"Negative news detected: {e.get('title', '')} (keywords: {', '.join(matched_kw)})",
                    "evidence_ids": [e.get("evidence_id", "")],
                })

    for e in evidence:
        if e.get("evidence_type") == "resource":
            if e.get("confidence", 1.0) < 0.7:
                risks.append({
                    "risk_id": "resource_low_confidence",
                    "severity": "low",
                    "description": f"Resource data for {e.get('metadata', {}).get('deposit_name', 'unknown')} has low extraction confidence ({e.get('confidence', 0):.2f}).",
                    "evidence_ids": [e.get("evidence_id", "")],
                })

    if price_trend and price_trend.get("is_demo"):
        risks.append({
            "risk_id": "data_source_demo",
            "severity": "low",
            "description": "Price data is sourced from demo fixtures, not live market data.",
            "evidence_ids": [e["evidence_id"] for e in evidence if e.get("evidence_type") == "price"],
        })

    for section, status in tool_status.items():
        if status in ("error", "unavailable"):
            risks.append({
                "risk_id": "missing_data_section",
                "severity": "medium",
                "description": f"Section '{section}' data could not be retrieved.",
                "evidence_ids": [],
            })

    return {"risks": risks}
