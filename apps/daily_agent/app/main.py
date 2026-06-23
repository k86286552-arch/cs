from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from fastapi import FastAPI

env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(env_path)

logging.basicConfig(
    stream=sys.stderr,
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = FastAPI(
    title="Mining Daily Brief Agent",
    version="0.1.0",
    description="Agent that generates daily mining briefs using MCP servers",
)

from app.api.routes import router  # noqa: E402
app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "Mining Daily Brief Agent",
        "version": "0.1.0",
        "docs": "/docs",
        "brief_endpoint": "/api/v1/briefs",
    }
