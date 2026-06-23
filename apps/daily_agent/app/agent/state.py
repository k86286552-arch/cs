from __future__ import annotations

from typing import TypedDict


class DailyBriefState(TypedDict, total=False):
    request_id: str
    user_query: str
    report_date: str
    requested_news_days: int
    requested_price_days: int

    parsed_intent: dict
    entity: dict
    plan: dict

    news_search_results: list[dict]
    articles: list[dict]
    resource_report: dict | None
    resource_rows: list[dict]
    price_result: dict | None
    price_trend: dict | None

    normalized_evidence: list[dict]
    warnings: list[dict]
    risks: list[dict]

    draft_markdown: str | None
    verification: dict | None
    revision_count: int
    final_markdown: str | None

    tool_status: dict
