from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent / "templates"


def render_daily_brief(
    project_name: str,
    company_name: str,
    report_date: str,
    summary: str,
    news_items: list[dict],
    news_status: str,
    resource_rows: list[dict],
    resource_status: str,
    trend: dict | None,
    price_status: str,
    risks: list[dict],
    evidence: list[dict],
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("daily_brief.md.j2")

    return template.render(
        project_name=project_name,
        company_name=company_name,
        report_date=report_date,
        summary=summary,
        news_items=news_items,
        news_status=news_status,
        resource_rows=resource_rows,
        resource_status=resource_status,
        trend=trend,
        price_status=price_status,
        risks=risks,
        evidence=evidence,
    )
