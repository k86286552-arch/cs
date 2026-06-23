from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[4] / "data" / "fixtures"


def _matches_project_hint(entry: dict, project_hint: str | None) -> bool:
    if not project_hint:
        return False

    hint = project_hint.strip().lower()
    if not hint:
        return False

    report = entry.get("report", {})
    haystacks = [
        report.get("project_name", ""),
        report.get("title", ""),
    ]
    haystacks.extend(row.get("deposit_name", "") for row in entry.get("resources", []))
    return any(hint in str(value).lower() for value in haystacks if value)


def load_resource_fixture(pdf_url: str, project_hint: str | None = None) -> dict | None:
    path = FIXTURE_DIR / "resources.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for entry in data:
        if entry.get("report", {}).get("pdf_url") == pdf_url:
            return entry
    for entry in data:
        if _matches_project_hint(entry, project_hint):
            return entry
    return None
