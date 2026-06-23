from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("daily-agent.mcp")

PROJECT_ROOT = Path(__file__).resolve().parents[4]

SERVER_CONFIGS: dict[str, dict] = {
    "mining-news-mcp": {
        "module": "app.server",
        "directory": str(PROJECT_ROOT / "mcp_servers" / "mining_news"),
        "env": {},
    },
    "mineral-pdf-mcp": {
        "module": "app.server",
        "directory": str(PROJECT_ROOT / "mcp_servers" / "mineral_pdf"),
        "env": {},
    },
    "lme-price-mcp": {
        "module": "app.server",
        "directory": str(PROJECT_ROOT / "mcp_servers" / "lme_price"),
        "env": {},
    },
}


class MCPClientManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._transports: dict[str, Any] = {}
        self._contexts: list[Any] = []

    async def connect_all(self) -> None:
        for name, cfg in SERVER_CONFIGS.items():
            try:
                await self._connect_server(name, cfg)
                logger.info("Connected to %s", name)
            except Exception as exc:
                logger.error("Failed to connect to %s: %s", name, exc)

    async def _connect_server(self, name: str, cfg: dict) -> None:
        env = {**os.environ, **cfg.get("env", {})}
        env.pop("VIRTUAL_ENV", None)
        params = StdioServerParameters(
            command="uv",
            args=["--directory", cfg["directory"], "run", "python", "-m", cfg["module"]],
            env=env,
        )
        ctx = stdio_client(params)
        transport = await ctx.__aenter__()
        self._contexts.append(ctx)

        read_stream, write_stream = transport
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        self._contexts.append(session)

        await session.initialize()
        self._sessions[name] = session

    async def call_tool(self, server: str, tool_name: str, arguments: dict) -> dict:
        session = self._sessions.get(server)
        if not session:
            return {
                "error_code": "INTERNAL_ERROR",
                "message": f"Server '{server}' not connected.",
                "retryable": False,
                "component": server,
            }

        try:
            result = await session.call_tool(tool_name, arguments)
            if result.content:
                text = result.content[0].text
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw_text": text}
            return {"raw_text": "", "warnings": ["Empty response from tool."]}
        except Exception as exc:
            logger.error("Tool call %s/%s failed: %s", server, tool_name, exc)
            return {
                "error_code": "INTERNAL_ERROR",
                "message": f"Tool call failed: {exc}",
                "retryable": True,
                "component": server,
            }

    async def list_tools(self, server: str) -> list[dict]:
        session = self._sessions.get(server)
        if not session:
            return []
        result = await session.list_tools()
        return [{"name": t.name, "description": t.description} for t in result.tools]

    async def close(self) -> None:
        for ctx in reversed(self._contexts):
            try:
                await ctx.__aexit__(None, None, None)
            except Exception:
                pass
        self._sessions.clear()
        self._transports.clear()
        self._contexts.clear()

    @property
    def connected_servers(self) -> list[str]:
        return list(self._sessions.keys())
