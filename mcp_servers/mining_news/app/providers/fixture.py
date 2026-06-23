from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[4] / "data" / "fixtures"
COMMODITY_TERMS = {
    "lithium",
    "copper",
    "nickel",
    "zinc",
    "gold",
    "iron",
    "ore",
    "carbonate",
    "li2o",
}
GENERIC_ENTITY_TERMS = {
    "minerals",
    "mineral",
    "mine",
    "mines",
    "project",
    "projects",
    "operation",
    "operations",
}


def load_news_fixtures() -> list[dict]:
    path = FIXTURE_DIR / "news.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def search_fixture_news(query: str, days: int = 1, limit: int = 10) -> list[dict]:
    items = load_news_fixtures()
    query_lower = query.lower()
    terms = query_lower.split()
    non_commodity_terms = [
        t for t in terms
        if t not in COMMODITY_TERMS and t not in GENERIC_ENTITY_TERMS
    ]

    results = []
    for item in items:
        text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        if non_commodity_terms and not any(t in text for t in non_commodity_terms):
            continue
        matched = [t for t in terms if t in text]
        if not matched:
            continue
        item["relevance_score"] = round(len(matched) / max(len(terms), 1), 2)
        item["matched_terms"] = matched
        results.append(item)

    results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return results[:limit]


def get_fixture_article(url: str) -> dict | None:
    items = load_news_fixtures()
    for item in items:
        if item.get("url") == url:
            return {
                "article_id": item.get("article_id", ""),
                "title": item.get("title", ""),
                "published_at": item.get("published_at"),
                "source_name": item.get("source_name", ""),
                "source_url": url,
                "content": item.get("content", item.get("snippet", "")),
                "summary": None,
                "parser": "fixture",
                "confidence": 0.95,
                "warnings": ["Fixture data is being used."],
            }
    return None
