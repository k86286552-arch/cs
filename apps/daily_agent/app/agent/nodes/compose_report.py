from __future__ import annotations

import logging
import os

from app.agent.state import DailyBriefState

logger = logging.getLogger("daily-agent.compose")

SUMMARY_SYSTEM_PROMPT = """You are a mining industry analyst. Based on the provided evidence (news, resource data, price data, risks), write a concise executive summary for a daily brief.

Requirements:
- Write 1-3 sentences capturing the most important developments
- Reference evidence IDs in brackets like [N1], [R1], [P1]
- Be factual and quantitative where possible
- Do not add information not present in the evidence"""


async def compose_report(state: DailyBriefState) -> dict:
    entity = state.get("entity", {})
    evidence = state.get("normalized_evidence", [])
    risks = state.get("risks", [])
    tool_status = state.get("tool_status", {})
    report_date = state.get("report_date", "")

    project_name = entity.get("project", "Unknown")
    company_name = entity.get("company", "Unknown")

    news_evidence = [e for e in evidence if e.get("evidence_type") == "news"]
    resource_evidence = [e for e in evidence if e.get("evidence_type") == "resource"]
    price_evidence = [e for e in evidence if e.get("evidence_type") == "price"]

    summary = await _generate_summary(evidence, risks)

    news_section = _build_news_section(news_evidence, tool_status.get("news", ""))
    resource_section = _build_resource_section(
        resource_evidence,
        state.get("resource_rows", []),
        tool_status.get("resources", ""),
    )
    price_section = _build_price_section(
        price_evidence,
        state.get("price_trend"),
        state.get("price_result"),
        tool_status.get("price", ""),
    )
    risk_section = _build_risk_section(risks)
    citation_section = _build_citation_section(evidence)

    markdown = f"""# {project_name} / {company_name} 今日简报

> 报告日期: {report_date}

## 1. 结论摘要
{summary}

## 2. 新闻摘要
{news_section}

## 3. 储量数据
{resource_section}

## 4. 价格走势
{price_section}

## 5. 风险提示
{risk_section}

## 6. 引用
{citation_section}
"""

    return {"draft_markdown": markdown}


async def _generate_summary(evidence: list[dict], risks: list[dict]) -> str:
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        return _fallback_summary(evidence, risks)

    try:
        from openai import AsyncOpenAI

        client_kwargs = {"api_key": api_key}
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        if base_url:
            client_kwargs["base_url"] = base_url
        client = AsyncOpenAI(**client_kwargs)

        evidence_text = "\n".join(
            f"[{e['evidence_id']}] ({e['evidence_type']}) {e['title']}: {e['content'][:200]}"
            for e in evidence
        )
        risk_text = "\n".join(f"- {r['description']}" for r in risks)

        response = await client.chat.completions.create(
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": f"Evidence:\n{evidence_text}\n\nRisks:\n{risk_text}"},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content or _fallback_summary(evidence, risks)
    except Exception as exc:
        logger.warning("LLM summary generation failed: %s", exc)
        return _fallback_summary(evidence, risks)


def _fallback_summary(evidence: list[dict], risks: list[dict]) -> str:
    parts: list[str] = []
    news = [e for e in evidence if e["evidence_type"] == "news"]
    if news:
        parts.append(f"本日共获取 {len(news)} 条相关新闻。{news[0].get('title', '')} [{news[0].get('evidence_id', '')}]。")
    resources = [e for e in evidence if e["evidence_type"] == "resource"]
    if resources:
        parts.append(f"储量数据包含 {len(resources)} 条记录。")
    prices = [e for e in evidence if e["evidence_type"] == "price"]
    if prices:
        parts.append(f"价格数据已获取 [{prices[0].get('evidence_id', '')}]。")
    if risks:
        high_risks = [r for r in risks if r.get("severity") == "high"]
        if high_risks:
            parts.append(f"注意: 存在 {len(high_risks)} 项高风险提示。")
    return "\n".join(f"- {p}" for p in parts) if parts else "- 暂无可用数据生成摘要。"


def _build_news_section(evidence: list[dict], status: str) -> str:
    if status in ("error", "unavailable"):
        return "本次未获得可验证的新闻数据，因此不对新闻趋势作结论。"
    if not evidence:
        return "本日未检索到相关新闻。"
    lines: list[str] = []
    for e in evidence:
        url_part = f" ([来源]({e['source_url']}))" if e.get("source_url") else ""
        lines.append(f"- {e.get('content', e.get('title', ''))[:200]} [{e['evidence_id']}]{url_part}")
    return "\n".join(lines)


def _build_resource_section(evidence: list[dict], rows: list[dict], status: str) -> str:
    if status in ("error", "unavailable"):
        return "本次未获得可验证的储量数据，因此不对储量作结论。"
    if not rows:
        return "未提取到储量数据。"

    header = "| 类别 | 矿石量 | 品位 | 含金属量 | 页码 | 证据 |"
    separator = "| --- | --- | --- | --- | --- | --- |"
    lines = [header, separator]

    for i, row in enumerate(rows):
        eid = f"R{i + 1}"
        tonnage = f"{row.get('ore_tonnage', '-')} {row.get('ore_tonnage_unit', '')}" if row.get("ore_tonnage") else "-"
        grade = f"{row.get('grade', '-')} {row.get('grade_unit', '')}" if row.get("grade") else "-"
        contained = str(row.get("contained_metal", "-") or "-")
        page = str(row.get("page_number", "-") or "-")
        lines.append(f"| {row.get('category', '-')} | {tonnage} | {grade} | {contained} | {page} | {eid} |")

    source_url = next((e.get("source_url") for e in evidence if e.get("source_url")), None)
    if source_url:
        lines.append(f"\n来源原文: {source_url}")

    return "\n".join(lines)


def _build_price_section(evidence: list[dict], trend: dict | None, price: dict | None, status: str) -> str:
    if status in ("error", "unavailable"):
        return "本次未获得可验证的价格数据，因此不对短期价格趋势作结论。"

    lines: list[str] = []
    if trend and "error_code" not in trend:
        period = trend.get("period", {})
        lines.append(f"- 过去 {period.get('days', 30)} 天价格变动: {trend.get('change_percent', 0):.2f}%")
        lines.append(
            f"- 起始价: {trend.get('start_price', '-')} -> 当前价: "
            f"{trend.get('end_price', '-')} {trend.get('currency', '')}/{trend.get('unit', '')}"
        )
        lines.append(f"- 区间最低: {trend.get('min_price', '-')} / 最高: {trend.get('max_price', '-')}")
        lines.append(f"- 数据源: {trend.get('source', 'unknown')}")
        if trend.get("source_url"):
            lines.append(f"- 来源链接: {trend.get('source_url')}")
        if trend.get("is_estimated"):
            lines.append("- 注记: 该价格趋势为基于公开网页摘要重建的近似结果，并非完整历史行情序列")
        if trend.get("is_demo"):
            lines.append("- 注意: 当前使用的是演示数据 (fixture)")
    elif price and "error_code" not in price:
        lines.append(
            f"- 当前价: {price.get('price', '-')} {price.get('currency', '')}/{price.get('unit', '')} "
            f"({price.get('date', '')})"
        )
        lines.append(f"- 数据源: {price.get('source', 'unknown')}")
        if price.get("source_url"):
            lines.append(f"- 来源链接: {price.get('source_url')}")
    else:
        lines.append("- 暂无可用价格数据。")

    price_eids = [e["evidence_id"] for e in evidence]
    if price_eids:
        lines.append(f"- 证据: {', '.join(price_eids)}")

    return "\n".join(lines)


def _build_risk_section(risks: list[dict]) -> str:
    if not risks:
        return "- 本日未检测到显著风险信号。"
    lines: list[str] = []
    for r in risks:
        severity_tag = {"high": "🔴", "medium": "🟠", "low": "🟢"}.get(r.get("severity", ""), "")
        eids = ", ".join(r.get("evidence_ids", []))
        ref = f" [{eids}]" if eids else ""
        lines.append(f"- {severity_tag} {r['description']}{ref}")
    return "\n".join(lines)


def _build_citation_section(evidence: list[dict]) -> str:
    lines: list[str] = []
    for e in evidence:
        eid = e["evidence_id"]
        etype = e["evidence_type"]
        if etype == "news":
            url = e.get("source_url", "")
            lines.append(f"- [{eid}] {e.get('title', '')} — {url}")
        elif etype == "resource":
            page = e.get("page_number", "?")
            url = e.get("source_url", "")
            if url:
                lines.append(f"- [{eid}] Technical Report p.{page} — {url}")
            else:
                lines.append(f"- [{eid}] Technical Report p.{page}")
        elif etype == "price":
            meta = e.get("metadata", {})
            date_text = meta.get("date", "")
            if not date_text:
                period = meta.get("period", {})
                start = period.get("start", "")
                end = period.get("end", "")
                if start and end:
                    date_text = f"{start} to {end}"
                else:
                    date_text = end or start or "date unavailable"
            base_text = (
                f"- [{eid}] {date_text} {meta.get('commodity', '')}, "
                f"{meta.get('currency', '')}/{meta.get('unit', '')}"
            )
            url = e.get("source_url", "")
            lines.append(f"{base_text} — {url}" if url else base_text)
    return "\n".join(lines) if lines else "- 无引用。"
