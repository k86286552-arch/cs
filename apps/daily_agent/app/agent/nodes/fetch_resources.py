from __future__ import annotations

import logging

from app.agent.state import DailyBriefState

logger = logging.getLogger("daily-agent.fetch_resources")


async def fetch_resources(state: DailyBriefState, mcp_manager) -> dict:
    plan = state.get("plan", {}).get("resources", {})
    if not plan.get("enabled") or not plan.get("pdf_url"):
        return {
            "resource_report": None,
            "resource_rows": [],
            "tool_status": {**state.get("tool_status", {}), "resources": "skipped"},
        }

    pdf_url = plan["pdf_url"]
    project_hint = plan.get("project_hint", "")
    categories = plan.get("categories", ["Indicated", "Inferred"])

    try:
        result = await mcp_manager.call_tool(
            "mineral-pdf-mcp",
            "extract_resources",
            {
                "pdf_url": pdf_url,
                "project_hint": project_hint,
                "categories": categories,
                "include_evidence": True,
            },
        )

        if "error_code" in result:
            logger.warning("Resource extraction error: %s", result.get("message"))
            return {
                "resource_report": None,
                "resource_rows": [],
                "tool_status": {**state.get("tool_status", {}), "resources": "error"},
                "warnings": state.get("warnings", []) + [{
                    "component": "resources",
                    "message": result.get("message", "Resource extraction failed."),
                }],
            }

        rows = result.get("resources", [])
        report = result.get("report", {})
        status = "success" if rows else "empty"

        return {
            "resource_report": report,
            "resource_rows": rows,
            "tool_status": {**state.get("tool_status", {}), "resources": status},
        }

    except Exception as exc:
        logger.error("Resource fetch failed: %s", exc)
        return {
            "resource_report": None,
            "resource_rows": [],
            "tool_status": {**state.get("tool_status", {}), "resources": "error"},
            "warnings": state.get("warnings", []) + [{
                "component": "resources",
                "message": f"Failed to extract resources: {exc}",
            }],
        }
