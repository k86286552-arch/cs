from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("mining-news-mcp")

mcp = FastMCP("mining-news-mcp")


def _get_data_mode() -> str:
    explicit = os.environ.get("NEWS_DATA_MODE", "").strip().lower()
    if explicit in {"live", "fixture"}:
        return explicit

    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    return "fixture" if app_env == "development" else "live"


USE_FIXTURE = _get_data_mode() == "fixture"


@mcp.tool()
async def search(query: str, days: int = 1, limit: int = 10) -> dict:
    """Search for mining news articles matching the query within the specified time range.

    Args:
        query: Search query, e.g. 'Pilbara Minerals lithium'
        days: Number of days to look back (1-90)
        limit: Maximum number of results (1-50)
    """
    logger.info("search called: query=%s days=%d limit=%d", query, days, limit)

    days = max(1, min(90, days))
    limit = max(1, min(50, limit))

    items: list[dict] = []
    warnings: list[str] = []

    if USE_FIXTURE:
        from app.providers.fixture import search_fixture_news
        items = search_fixture_news(query, days, limit)
        if not items:
            warnings.append("No fixture news matched the query.")
    else:
        try:
            from app.providers.rss import search_rss
            items = await search_rss(query, days, limit)
        except Exception as exc:
            logger.error("RSS search failed: %s", exc)
            return {
                "error_code": "NEWS_SEARCH_FAILED",
                "message": f"Live news search failed: {exc}",
                "retryable": True,
                "component": "news",
            }

    return {
        "query": query,
        "days": days,
        "total": len(items),
        "items": items,
        "warnings": warnings,
    }


@mcp.tool()
async def fetch_article(url: str) -> dict:
    """Fetch and extract the full content of a news article by URL.

    Args:
        url: The article URL to fetch
    """
    logger.info("fetch_article called: url=%s", url)

    if not url or not url.startswith(("http://", "https://")):
        return {
            "error_code": "INVALID_ARGUMENT",
            "message": f"Invalid URL: '{url}'. Must be http or https.",
            "retryable": False,
            "component": "news",
        }

    if USE_FIXTURE:
        from app.providers.fixture import get_fixture_article
        result = get_fixture_article(url)
        if result:
            return result

    try:
        from app.providers.article import fetch_article_content
        return await fetch_article_content(url)
    except ValueError as exc:
        return {
            "error_code": "INVALID_ARGUMENT",
            "message": str(exc),
            "retryable": False,
            "component": "news",
        }
    except Exception as exc:
        logger.error("Article fetch failed: %s", exc)
        return {
            "error_code": "ARTICLE_PARSE_FAILED",
            "message": f"Failed to fetch article: {exc}",
            "retryable": True,
            "component": "news",
        }


if __name__ == "__main__":
    mcp.run(transport="stdio")
