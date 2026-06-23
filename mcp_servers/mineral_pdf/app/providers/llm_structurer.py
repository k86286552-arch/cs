from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("mineral-pdf-mcp")

SYSTEM_PROMPT = """You are a mining technical report analyst. Given raw text from a mineral resource table page, extract structured resource data.

Return JSON array with objects containing:
- category: "Measured", "Indicated", "Inferred", or "Measured+Indicated"
- ore_tonnage: number (in Mt)
- grade: number
- grade_unit: string (e.g. "% Li2O", "% Cu")
- contained_metal: number or null
- evidence_text: the exact source text for this row

Only extract data that is explicitly present. Never invent numbers."""


async def structure_with_llm(page_texts: list[dict]) -> list[dict]:
    provider = os.environ.get("LLM_PROVIDER", "openai")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        logger.warning("No LLM API key configured, skipping LLM structuring")
        return []

    combined_text = "\n\n".join(
        f"--- Page {p['page_number']} ---\n{p['text'][:3000]}"
        for p in page_texts
    )

    try:
        from openai import AsyncOpenAI
        client_kwargs = {"api_key": api_key}
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        if base_url:
            client_kwargs["base_url"] = base_url
        client = AsyncOpenAI(**client_kwargs)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": combined_text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        return data.get("resources", []) if isinstance(data, dict) else data
    except Exception as exc:
        logger.error("LLM structuring failed: %s", exc)
        return []
