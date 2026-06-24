from __future__ import annotations

import re


def verify_citations(markdown: str, evidence: list[dict]) -> list[str]:
    issues: list[str] = []

    referenced_ids = set(re.findall(r"\[([NRP]\d+)\]", markdown))
    available_ids = {e["evidence_id"] for e in evidence}

    for ref_id in referenced_ids:
        if ref_id not in available_ids:
            issues.append(f"Citation [{ref_id}] referenced but not found in evidence.")

    for e in evidence:
        eid = e["evidence_id"]
        etype = e.get("evidence_type", "")
        if etype == "news" and not e.get("source_url"):
            issues.append(f"[{eid}] News evidence missing source URL.")
        if etype == "resource" and not e.get("source_url"):
            issues.append(f"[{eid}] Resource evidence missing source URL.")
        if etype == "resource" and not e.get("page_number"):
            issues.append(f"[{eid}] Resource evidence missing page number.")
        if etype == "price":
            meta = e.get("metadata", {})
            if not meta.get("date"):
                issues.append(f"[{eid}] Price evidence missing date.")
            if not meta.get("currency"):
                issues.append(f"[{eid}] Price evidence missing currency.")
            if meta.get("source") != "fixture" and not e.get("source_url"):
                issues.append(f"[{eid}] Non-fixture price evidence missing source URL.")

    return issues
