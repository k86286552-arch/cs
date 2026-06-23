from __future__ import annotations

import re

from app.agent.state import DailyBriefState

REQUIRED_SECTIONS = ["新闻摘要", "储量数据", "价格走势", "风险提示", "引用"]


async def final_verify(state: DailyBriefState) -> dict:
    md = state.get("draft_markdown", "")
    if not md:
        return {
            "final_markdown": "# 报告生成失败\n\n无法生成简报，请检查数据源可用性。",
            "verification": {"passed": False, "issues": ["No draft markdown generated."]},
        }

    issues: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in md:
            issues.append(f"Missing required section: {section}")

    evidence_ids = re.findall(r"\[([NRP]\d+)\]", md)
    citation_section = md.split("## 6. 引用")[-1] if "## 6. 引用" in md else ""
    for eid in set(evidence_ids):
        if eid not in citation_section:
            issues.append(f"Evidence {eid} referenced but not in citation section")

    if issues:
        md += "\n\n---\n\n> ⚠ 报告验证发现以下问题:\n"
        for issue in issues:
            md += f"> - {issue}\n"

    return {
        "final_markdown": md,
        "verification": {"passed": len(issues) == 0, "issues": issues},
        "revision_count": state.get("revision_count", 0) + 1,
    }
