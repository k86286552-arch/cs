from __future__ import annotations

import re


REQUIRED_SECTIONS = [
    "新闻摘要",
    "储量数据",
    "价格走势",
    "风险提示",
    "引用",
]


def verify_report_structure(markdown: str) -> list[str]:
    issues: list[str] = []

    for section in REQUIRED_SECTIONS:
        if section not in markdown:
            issues.append(f"Missing required section: '{section}'")

    if "引用" in markdown:
        citation_block = markdown.split("引用")[-1]
        evidence_refs = set(re.findall(r"\[([NRP]\d+)\]", markdown.split("引用")[0]))
        citation_refs = set(re.findall(r"\[([NRP]\d+)\]", citation_block))

        for ref in evidence_refs:
            if ref not in citation_refs:
                issues.append(f"Evidence [{ref}] used in report body but missing from citation section")
    else:
        issues.append("Citation section is completely missing")

    return issues
