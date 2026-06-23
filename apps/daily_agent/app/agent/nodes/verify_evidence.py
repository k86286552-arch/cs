from __future__ import annotations

from app.agent.state import DailyBriefState


async def verify_evidence(state: DailyBriefState) -> dict:
    evidence = state.get("normalized_evidence", [])
    warnings = list(state.get("warnings", []))
    verified: list[dict] = []

    for item in evidence:
        issues: list[str] = []
        etype = item.get("evidence_type", "")

        if etype == "news":
            if not item.get("source_url"):
                issues.append("Missing source URL")
            if not item.get("title"):
                issues.append("Missing title")
        elif etype == "resource":
            if not item.get("page_number"):
                issues.append("Missing page number")
            meta = item.get("metadata", {})
            if meta.get("ore_tonnage") is not None and meta.get("grade") is not None:
                if meta["ore_tonnage"] <= 0 or meta["grade"] <= 0:
                    issues.append("Invalid tonnage or grade values")
        elif etype == "price":
            meta = item.get("metadata", {})
            if meta.get("is_demo"):
                issues.append("Using demo/fixture data")

        item["verification_issues"] = issues
        if issues:
            warnings.append({
                "component": etype,
                "evidence_id": item.get("evidence_id", ""),
                "issues": issues,
            })
        verified.append(item)

    return {
        "normalized_evidence": verified,
        "warnings": warnings,
        "verification": {
            "total": len(verified),
            "with_issues": sum(1 for v in verified if v.get("verification_issues")),
            "clean": sum(1 for v in verified if not v.get("verification_issues")),
        },
    }
