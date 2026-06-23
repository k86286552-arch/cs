from __future__ import annotations

import logging

from app.agent.state import DailyBriefState

logger = logging.getLogger("daily-agent.fetch_news")


async def fetch_news(state: DailyBriefState, mcp_manager) -> dict:
    plan = state.get("plan", {}).get("news", {})
    if not plan.get("enabled"):
        return {
            "news_search_results": [],
            "articles": [],
            "tool_status": {**state.get("tool_status", {}), "news": "skipped"},
        }

    queries = plan.get("queries", [])
    days = plan.get("days", 1)
    limit = plan.get("limit", 10)
    fetch_top = plan.get("fetch_top_articles", 5)

    all_items: list[dict] = []
    seen_urls: set[str] = set()
    warnings: list[dict] = []
    had_error = False

    for query in queries:
        try:
            result = await mcp_manager.call_tool(
                "mining-news-mcp",
                "search",
                {"query": query, "days": days, "limit": limit},
            )
            if "error_code" in result:
                logger.warning("News search error: %s", result.get("message"))
                had_error = True
                warnings.append({
                    "component": "news",
                    "query": query,
                    "message": result.get("message", "News search failed."),
                })
                continue

            for item in result.get("items", []):
                url = item.get("url", "")
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_items.append(item)
        except Exception as exc:
            logger.error("News search failed for '%s': %s", query, exc)
            had_error = True
            warnings.append({
                "component": "news",
                "query": query,
                "message": f"News search failed: {exc}",
            })

    all_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    articles: list[dict] = []
    for item in all_items[:fetch_top]:
        url = item.get("url", "")
        if not url:
            continue
        try:
            article = await mcp_manager.call_tool(
                "mining-news-mcp",
                "fetch_article",
                {"url": url},
            )
            if "error_code" not in article:
                articles.append(article)
        except Exception as exc:
            logger.warning("Article fetch failed for %s: %s", url, exc)

    if all_items:
        status = "success"
    elif had_error:
        status = "unavailable"
    else:
        status = "empty"
    return {
        "news_search_results": all_items,
        "articles": articles,
        "tool_status": {**state.get("tool_status", {}), "news": status},
        "warnings": warnings,
    }
