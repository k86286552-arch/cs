from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date
from typing import Any

from langgraph.graph import StateGraph, END

from app.agent.state import DailyBriefState
from app.agent.nodes.parse_query import parse_query
from app.agent.nodes.resolve_entity import resolve_entity
from app.agent.nodes.build_plan import build_plan
from app.agent.nodes.fetch_news import fetch_news
from app.agent.nodes.fetch_resources import fetch_resources
from app.agent.nodes.fetch_prices import fetch_prices
from app.agent.nodes.normalize import normalize_results
from app.agent.nodes.verify_evidence import verify_evidence
from app.agent.nodes.analyze_risks import analyze_risks
from app.agent.nodes.compose_report import compose_report
from app.agent.nodes.final_verify import final_verify
from app.mcp_client.manager import MCPClientManager

logger = logging.getLogger("daily-agent.graph")


class DailyBriefAgent:
    def __init__(self) -> None:
        self.mcp = MCPClientManager()
        self._graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        g = StateGraph(DailyBriefState)

        g.add_node("parse_query", parse_query)
        g.add_node("resolve_entity", resolve_entity)
        g.add_node("build_plan", build_plan)
        g.add_node("fetch_data", self._fetch_data_parallel)
        g.add_node("normalize", normalize_results)
        g.add_node("verify_evidence", verify_evidence)
        g.add_node("analyze_risks", analyze_risks)
        g.add_node("compose_report", compose_report)
        g.add_node("final_verify", final_verify)

        g.set_entry_point("parse_query")
        g.add_edge("parse_query", "resolve_entity")
        g.add_edge("resolve_entity", "build_plan")
        g.add_edge("build_plan", "fetch_data")
        g.add_edge("fetch_data", "normalize")
        g.add_edge("normalize", "verify_evidence")
        g.add_edge("verify_evidence", "analyze_risks")
        g.add_edge("analyze_risks", "compose_report")
        g.add_edge("compose_report", "final_verify")
        g.add_edge("final_verify", END)

        return g

    async def _fetch_data_parallel(self, state: DailyBriefState) -> dict:
        state["tool_status"] = state.get("tool_status", {})

        async def _safe_fetch_news():
            try:
                return await fetch_news(state, self.mcp)
            except Exception as exc:
                logger.error("News fetch error: %s", exc)
                return {
                    "news_search_results": [],
                    "articles": [],
                    "tool_status": {"news": "error"},
                }

        async def _safe_fetch_resources():
            try:
                return await fetch_resources(state, self.mcp)
            except Exception as exc:
                logger.error("Resource fetch error: %s", exc)
                return {
                    "resource_report": None,
                    "resource_rows": [],
                    "tool_status": {"resources": "error"},
                }

        async def _safe_fetch_prices():
            try:
                return await fetch_prices(state, self.mcp)
            except Exception as exc:
                logger.error("Price fetch error: %s", exc)
                return {
                    "price_result": None,
                    "price_trend": None,
                    "tool_status": {"price": "error"},
                }

        news_result, resource_result, price_result = await asyncio.gather(
            _safe_fetch_news(),
            _safe_fetch_resources(),
            _safe_fetch_prices(),
        )

        merged: dict[str, Any] = {}
        merged_status: dict[str, str] = {}

        for result in [news_result, resource_result, price_result]:
            ts = result.pop("tool_status", {})
            merged_status.update(ts)
            merged.update(result)

        merged["tool_status"] = merged_status
        merged["warnings"] = (
            state.get("warnings", [])
            + news_result.get("warnings", [])
            + resource_result.get("warnings", [])
            + price_result.get("warnings", [])
        )

        return merged

    async def run(
        self,
        query: str,
        *,
        news_days: int | None = None,
        price_days: int | None = None,
    ) -> dict:
        request_id = f"req_{date.today().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"

        initial_state: DailyBriefState = {
            "request_id": request_id,
            "user_query": query,
            "report_date": date.today().isoformat(),
            "warnings": [],
            "risks": [],
            "tool_status": {},
            "revision_count": 0,
        }
        if news_days is not None:
            initial_state["requested_news_days"] = news_days
        if price_days is not None:
            initial_state["requested_price_days"] = price_days

        logger.info("Starting daily brief: %s", request_id)

        await self.mcp.connect_all()

        try:
            compiled = self._graph.compile()
            final_state = await compiled.ainvoke(initial_state)

            return {
                "request_id": request_id,
                "status": "completed",
                "entity": final_state.get("entity", {}),
                "markdown": final_state.get("final_markdown", ""),
                "warnings": final_state.get("warnings", []),
                "tool_status": final_state.get("tool_status", {}),
                "verification": final_state.get("verification", {}),
            }
        finally:
            await self.mcp.close()
