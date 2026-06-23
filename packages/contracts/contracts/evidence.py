from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: Literal["news", "resource", "price"]
    title: str
    content: str
    source_url: str | None = None
    published_at: datetime | None = None
    page_number: int | None = None
    source_name: str = ""
    confidence: float = 0.0
    metadata: dict = {}
