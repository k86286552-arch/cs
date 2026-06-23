from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx

RSS_FEEDS = [
    {"name": "MINING.COM", "url": "https://www.mining.com/feed/"},
    {"name": "Mining Weekly", "url": "https://www.miningweekly.com/page/rss"},
]

HEADERS = {"User-Agent": "MineralDailyAgent/0.1 (research-bot)"}
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


def _article_id(url: str) -> str:
    return "news_" + hashlib.md5(url.encode()).hexdigest()[:8]


def _parse_date(entry: dict) -> datetime | None:
    for field in ("published", "updated"):
        val = entry.get(field)
        if val:
            try:
                return parsedate_to_datetime(val)
            except Exception:
                pass
    return None


def _relevance_score(title: str, snippet: str, query_terms: list[str]) -> tuple[float, list[str]]:
    text = (title + " " + snippet).lower()
    matched = [t for t in query_terms if t.lower() in text]
    if not query_terms:
        return 0.5, []

    non_commodity_terms = [
        t for t in query_terms
        if t.lower() not in COMMODITY_TERMS and t.lower() not in GENERIC_ENTITY_TERMS
    ]
    if non_commodity_terms and not any(term.lower() in text for term in non_commodity_terms):
        return 0.0, []

    return round(len(matched) / len(query_terms), 2), matched


async def search_rss(query: str, days: int = 1, limit: int = 10) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query_terms = [t.strip() for t in query.split() if t.strip()]
    results: list[dict] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(timeout=15, headers=HEADERS, follow_redirects=True) as client:
        for feed_info in RSS_FEEDS:
            try:
                resp = await client.get(feed_info["url"])
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
            except Exception:
                continue

            for entry in feed.entries:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue

                pub_date = _parse_date(entry)
                if pub_date and pub_date < cutoff:
                    continue

                title = entry.get("title", "")
                snippet = entry.get("summary", "")[:300]
                score, matched = _relevance_score(title, snippet, query_terms)

                if score < 0.3 and query_terms:
                    continue

                seen_urls.add(url)
                results.append({
                    "article_id": _article_id(url),
                    "title": title,
                    "url": url,
                    "source_name": feed_info["name"],
                    "published_at": pub_date.isoformat() if pub_date else "",
                    "snippet": snippet,
                    "relevance_score": score,
                    "matched_terms": matched,
                })

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:limit]
