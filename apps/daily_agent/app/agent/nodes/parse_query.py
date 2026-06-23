from __future__ import annotations

import re
from datetime import date

from app.agent.state import DailyBriefState


async def parse_query(state: DailyBriefState) -> dict:
    query = state.get("user_query", "")
    today = date.today().isoformat()

    target_text = query
    for prefix in ["给我生成一份关于", "生成一份关于", "给我一份", "生成", "关于"]:
        if target_text.startswith(prefix):
            target_text = target_text[len(prefix):]
    for suffix in ["的今日简报", "的简报", "今日简报", "简报", "的报告", "报告"]:
        if target_text.endswith(suffix):
            target_text = target_text[:-len(suffix)]
    target_text = target_text.strip()

    days_match = re.search(r"(\d+)\s*[天日]", query)
    news_days = int(days_match.group(1)) if days_match else 1

    price_days_match = re.search(r"(\d+)\s*[天日]?趋势", query)
    price_days = int(price_days_match.group(1)) if price_days_match else 30

    requested_news_days = state.get("requested_news_days")
    requested_price_days = state.get("requested_price_days")
    if requested_news_days is not None:
        news_days = requested_news_days
    if requested_price_days is not None:
        price_days = requested_price_days

    return {
        "parsed_intent": {
            "intent": "daily_mining_brief",
            "target_text": target_text,
            "report_date": today,
            "news_days": news_days,
            "price_days": price_days,
            "requested_sections": ["news", "resources", "price", "risks"],
        },
        "report_date": today,
    }
