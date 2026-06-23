from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import BriefRequest, BriefResponse
from app.agent.graph import DailyBriefAgent

logger = logging.getLogger("daily-agent.api")
router = APIRouter(prefix="/api/v1")


@router.post("/briefs", response_model=BriefResponse)
async def create_brief(req: BriefRequest) -> BriefResponse:
    logger.info("Brief request: %s", req.query)

    try:
        agent = DailyBriefAgent()
        result = await agent.run(
            req.query,
            news_days=req.news_days,
            price_days=req.price_days,
        )

        return BriefResponse(
            request_id=result.get("request_id", ""),
            status=result.get("status", "completed"),
            entity=result.get("entity", {}),
            markdown=result.get("markdown", ""),
            warnings=result.get("warnings", []),
            tool_status=result.get("tool_status", {}),
        )
    except Exception as exc:
        logger.error("Brief generation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "daily-agent"}
