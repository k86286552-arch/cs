from __future__ import annotations

from datetime import datetime

from app.agent.state import DailyBriefState


def _make_evidence_id(etype: str, idx: int) -> str:
    prefix = {"news": "N", "resource": "R", "price": "P"}.get(etype, "X")
    return f"{prefix}{idx}"


async def normalize_results(state: DailyBriefState) -> dict:
    evidence: list[dict] = []
    idx_news = 1
    idx_res = 1
    idx_price = 1

    for article in state.get("articles", []):
        eid = _make_evidence_id("news", idx_news)
        idx_news += 1
        evidence.append({
            "evidence_id": eid,
            "evidence_type": "news",
            "title": article.get("title", ""),
            "content": article.get("content", article.get("snippet", ""))[:500],
            "source_url": article.get("source_url", article.get("url", "")),
            "published_at": article.get("published_at"),
            "page_number": None,
            "source_name": article.get("source_name", ""),
            "confidence": article.get("confidence", 0.0),
            "metadata": {},
        })

    if not evidence:
        for item in state.get("news_search_results", []):
            eid = _make_evidence_id("news", idx_news)
            idx_news += 1
            evidence.append({
                "evidence_id": eid,
                "evidence_type": "news",
                "title": item.get("title", ""),
                "content": item.get("snippet", ""),
                "source_url": item.get("url", ""),
                "published_at": item.get("published_at"),
                "page_number": None,
                "source_name": item.get("source_name", ""),
                "confidence": item.get("relevance_score", 0.0),
                "metadata": {},
            })

    for row in state.get("resource_rows", []):
        eid = _make_evidence_id("resource", idx_res)
        idx_res += 1
        evidence.append({
            "evidence_id": eid,
            "evidence_type": "resource",
            "title": f"{row.get('category', '')} - {row.get('deposit_name', '')}",
            "content": row.get("evidence_text", ""),
            "source_url": state.get("resource_report", {}).get("pdf_url") if state.get("resource_report") else None,
            "published_at": None,
            "page_number": row.get("page_number"),
            "source_name": "Technical Report",
            "confidence": row.get("confidence", 0.0),
            "metadata": row,
        })

    price_result = state.get("price_result")
    if price_result and "error_code" not in price_result:
        eid = _make_evidence_id("price", idx_price)
        idx_price += 1
        evidence.append({
            "evidence_id": eid,
            "evidence_type": "price",
            "title": f"{price_result.get('commodity', '')} price on {price_result.get('date', '')}",
            "content": f"{price_result.get('price', '')} {price_result.get('currency', '')}/{price_result.get('unit', '')}",
            "source_url": price_result.get("source_url"),
            "published_at": price_result.get("date"),
            "page_number": None,
            "source_name": price_result.get("source", ""),
            "confidence": 1.0 if not price_result.get("is_demo") else 0.7,
            "metadata": price_result,
        })

    price_trend = state.get("price_trend")
    if price_trend and "error_code" not in price_trend:
        eid = _make_evidence_id("price", idx_price)
        idx_price += 1
        period = price_trend.get("period", {})
        evidence.append({
            "evidence_id": eid,
            "evidence_type": "price",
            "title": f"{price_trend.get('commodity', '')} {period.get('days', 30)}-day trend",
            "content": f"Change: {price_trend.get('change_percent', 0):.2f}% ({price_trend.get('start_price', '')} -> {price_trend.get('end_price', '')})",
            "source_url": price_trend.get("source_url"),
            "published_at": period.get("end"),
            "page_number": None,
            "source_name": price_trend.get("source", ""),
            "confidence": 0.85 if price_trend.get("is_estimated") else (1.0 if not price_trend.get("is_demo") else 0.7),
            "metadata": price_trend,
        })

    return {"normalized_evidence": evidence}
