from __future__ import annotations

from pydantic import BaseModel, Field


class BriefRequest(BaseModel):
    query: str = Field(description="User query, e.g. '给我生成一份关于 Pilbara 锂矿的今日简报'")
    news_days: int = Field(default=1, ge=1, le=90)
    price_days: int = Field(default=30, ge=2, le=365)
    output_format: str = Field(default="markdown")


class BriefResponse(BaseModel):
    request_id: str
    status: str
    entity: dict = {}
    markdown: str = ""
    warnings: list = []
    tool_status: dict = {}
