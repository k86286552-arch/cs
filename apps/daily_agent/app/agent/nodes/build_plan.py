from __future__ import annotations

from app.agent.state import DailyBriefState


async def build_plan(state: DailyBriefState) -> dict:
    intent = state.get("parsed_intent", {})
    entity = state.get("entity", {})

    news_queries = entity.get("news_queries", [])
    if not news_queries:
        company = entity.get("company", "")
        commodity = entity.get("commodity", "")
        news_queries = [f"{company} {commodity}".strip()]

    price_cfg = entity.get("price_benchmark", {})
    reports = entity.get("technical_reports", [])

    plan = {
        "news": {
            "enabled": True,
            "queries": news_queries,
            "days": intent.get("news_days", 1),
            "limit": 10,
            "fetch_top_articles": 5,
        },
        "resources": {
            "enabled": bool(reports),
            "pdf_url": reports[0]["url"] if reports else None,
            "project_hint": entity.get("project", ""),
            "categories": ["Indicated", "Inferred"],
        },
        "price": {
            "enabled": bool(price_cfg),
            "commodity": price_cfg.get("commodity", entity.get("commodity", "")),
            "benchmark": price_cfg.get("benchmark"),
            "days": intent.get("price_days", 30),
        },
    }

    return {"plan": plan}
