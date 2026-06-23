from __future__ import annotations

import logging
from pathlib import Path

import yaml

from app.agent.state import DailyBriefState

logger = logging.getLogger("daily-agent.resolve")

PROJECT_ROOT = Path(__file__).resolve().parents[5]
REGISTRY_PATH = PROJECT_ROOT / "config" / "project_registry.yaml"


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {}
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


async def resolve_entity(state: DailyBriefState) -> dict:
    intent = state.get("parsed_intent", {})
    target_text = intent.get("target_text", "")
    target_lower = target_text.lower()

    registry = _load_registry()
    projects = registry.get("projects", {})

    best_match = None
    best_score = 0.0
    matched_aliases: list[str] = []

    for key, project in projects.items():
        aliases = [a.lower() for a in project.get("aliases", [])]
        aliases.append(key.lower())
        aliases.append(project.get("display_name", "").lower())
        aliases.append(project.get("company", "").lower())

        score = 0.0
        hits: list[str] = []
        for alias in aliases:
            if alias and alias in target_lower:
                match_len = len(alias) / max(len(target_lower), 1)
                score = max(score, 0.5 + match_len * 0.5)
                hits.append(alias)
            elif target_lower in alias:
                score = max(score, 0.4)
                hits.append(alias)

        if score > best_score:
            best_score = score
            best_match = project
            matched_aliases = hits

    if best_match and best_score >= 0.3:
        entity = {
            "company": best_match.get("company", ""),
            "project": best_match.get("display_name", ""),
            "commodity": best_match.get("commodities", ["unknown"])[0],
            "country": best_match.get("country", ""),
            "region": best_match.get("region", ""),
            "confidence": round(best_score, 2),
            "aliases_matched": matched_aliases,
            "news_queries": best_match.get("news_queries", []),
            "price_benchmark": best_match.get("price_benchmark", {}),
            "technical_reports": best_match.get("technical_reports", []),
            "warnings": [],
        }
        logger.info("Resolved entity: %s (confidence: %.2f)", entity["project"], best_score)
        return {"entity": entity}

    logger.warning("Could not resolve entity for: %s", target_text)
    return {
        "entity": {
            "company": target_text,
            "project": target_text,
            "commodity": "unknown",
            "country": "",
            "region": "",
            "confidence": 0.0,
            "aliases_matched": [],
            "news_queries": [target_text],
            "price_benchmark": {},
            "technical_reports": [],
            "warnings": [f"Could not resolve '{target_text}' to a known project."],
        }
    }
