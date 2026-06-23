from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field, AnyHttpUrl


# ─── mining-news-mcp ───

class SearchNewsInput(BaseModel):
    query: str
    days: int = Field(default=1, ge=1, le=90)
    limit: int = Field(default=10, ge=1, le=50)


class NewsItem(BaseModel):
    article_id: str
    title: str
    url: str
    source_name: str
    published_at: str
    snippet: str
    relevance_score: float = 0.0
    matched_terms: list[str] = []


class SearchNewsOutput(BaseModel):
    query: str
    days: int
    total: int
    items: list[NewsItem]
    warnings: list[str] = []


class FetchArticleInput(BaseModel):
    url: str


class FetchArticleOutput(BaseModel):
    article_id: str
    title: str
    published_at: str | None = None
    source_name: str
    source_url: str
    content: str
    summary: str | None = None
    parser: str = "trafilatura"
    confidence: float = 0.0
    warnings: list[str] = []


# ─── mineral-pdf-mcp ───

class ExtractResourcesInput(BaseModel):
    pdf_url: str
    project_hint: str | None = None
    categories: list[str] = Field(default=["Indicated", "Inferred"])
    commodities: list[str] = Field(default=[])
    include_evidence: bool = True


class ReportMeta(BaseModel):
    title: str
    project_name: str
    effective_date: str | None = None
    pdf_url: str


class ResourceRow(BaseModel):
    deposit_name: str
    category: str
    commodity: str
    ore_tonnage: float | None = None
    ore_tonnage_unit: str = "Mt"
    grade: float | None = None
    grade_unit: str = ""
    contained_metal: float | None = None
    contained_metal_unit: str | None = None
    page_number: int | None = None
    table_title: str | None = None
    evidence_text: str | None = None
    confidence: float = 0.0


class ExtractResourcesOutput(BaseModel):
    report: ReportMeta
    resources: list[ResourceRow]
    warnings: list[str] = []
    status: str = "success"


# ─── lme-price-mcp ───

class GetPriceInput(BaseModel):
    commodity: str
    date: date
    benchmark: str | None = None


class GetPriceOutput(BaseModel):
    commodity: str
    benchmark: str
    date: str
    price: float
    currency: str = "USD"
    unit: str = "tonne"
    price_type: str = "official_close"
    source: str = "fixture"
    is_delayed: bool = False
    is_demo: bool = False
    warnings: list[str] = []


class TrendPoint(BaseModel):
    date: str
    price: float


class GetTrendInput(BaseModel):
    commodity: str
    days: int = Field(default=30, ge=2, le=365)
    benchmark: str | None = None


class GetTrendOutput(BaseModel):
    commodity: str
    benchmark: str
    period: dict
    start_price: float
    end_price: float
    change: float
    change_percent: float
    min_price: float
    max_price: float
    currency: str = "USD"
    unit: str = "tonne"
    points: list[TrendPoint]
    source: str = "fixture"
    is_demo: bool = False
    warnings: list[str] = []
