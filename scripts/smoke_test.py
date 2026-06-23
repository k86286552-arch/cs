"""Smoke test: verify all three MCP servers start and respond to tool calls."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ENV = os.environ.get("APP_ENV", "development")
NEWS_DATA_MODE = os.environ.get("NEWS_DATA_MODE", "fixture")
PDF_DATA_MODE = os.environ.get("PDF_DATA_MODE", "fixture")
PRICE_DATA_MODE = os.environ.get("PRICE_DATA_MODE", "fixture")

SERVERS = {
    "lme-price-mcp": {
        "directory": str(PROJECT_ROOT / "mcp_servers" / "lme_price"),
        "module": "app.server",
        "env": {
            "APP_ENV": APP_ENV,
            "PRICE_DATA_MODE": PRICE_DATA_MODE,
            "PRICE_LIVE_BASE_URL": os.environ.get("PRICE_LIVE_BASE_URL", ""),
            "PRICE_LIVE_API_KEY": os.environ.get("PRICE_LIVE_API_KEY", ""),
            "PRICE_LIVE_TIMEOUT_SECONDS": os.environ.get("PRICE_LIVE_TIMEOUT_SECONDS", "30"),
            "PRICE_PUBLIC_WEB_ENABLED": os.environ.get("PRICE_PUBLIC_WEB_ENABLED", "1"),
            "PRICE_PUBLIC_WEB_TIMEOUT_SECONDS": os.environ.get("PRICE_PUBLIC_WEB_TIMEOUT_SECONDS", "30"),
        },
        "test_call": ("get_price", {"commodity": "lithium_carbonate", "date": "2026-06-22"}),
    },
    "mining-news-mcp": {
        "directory": str(PROJECT_ROOT / "mcp_servers" / "mining_news"),
        "module": "app.server",
        "env": {"APP_ENV": APP_ENV, "NEWS_DATA_MODE": NEWS_DATA_MODE},
        "test_call": ("search", {"query": "Pilbara Minerals lithium", "days": 1, "limit": 5}),
    },
    "mineral-pdf-mcp": {
        "directory": str(PROJECT_ROOT / "mcp_servers" / "mineral_pdf"),
        "module": "app.server",
        "env": {
            "APP_ENV": APP_ENV,
            "PDF_DATA_MODE": PDF_DATA_MODE,
            "LLM_PROVIDER": os.environ.get("LLM_PROVIDER", ""),
            "LLM_API_KEY": os.environ.get("LLM_API_KEY", ""),
            "LLM_MODEL": os.environ.get("LLM_MODEL", ""),
            "LLM_BASE_URL": os.environ.get("LLM_BASE_URL", ""),
        },
        "test_call": ("extract_resources", {
            "pdf_url": "https://pls.com/wp-content/uploads/2025/08/2025AnnualReportincorporatingAppendix4E.pdf",
            "project_hint": "Pilgangoora Operation",
        }),
    },
}


async def test_server(name: str, cfg: dict) -> bool:
    print(f"\n{'='*50}")
    print(f"Testing: {name}")
    print(f"{'='*50}")

    env = {**os.environ, **cfg.get("env", {})}
    env.pop("VIRTUAL_ENV", None)
    params = StdioServerParameters(
        command="uv",
        args=["--directory", cfg["directory"], "run", "python", "-m", cfg["module"]],
        env=env,
    )

    try:
        async with stdio_client(params) as transport:
            read_stream, write_stream = transport
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print(f"  [OK] Connected and initialized")

                tools_result = await session.list_tools()
                tools = [t.name for t in tools_result.tools]
                print(f"  [OK] tools/list: {tools}")

                tool_name, args = cfg["test_call"]
                result = await session.call_tool(tool_name, args)
                if result.content:
                    text = result.content[0].text
                    data = json.loads(text)
                    if "error_code" in data:
                        print(f"  [WARN] Tool returned error: {data.get('error_code')}: {data.get('message')}")
                    else:
                        print(f"  [OK] tools/call '{tool_name}': success")
                        preview = json.dumps(data, indent=2, ensure_ascii=False)[:500]
                        print(f"  Response preview:\n{preview}")
                else:
                    print(f"  [WARN] Empty response from {tool_name}")

                return True

    except Exception as exc:
        print(f"  [FAIL] {exc}")
        return False


async def main() -> None:
    print("Mining Daily Agent - Smoke Test")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"APP_ENV={APP_ENV} NEWS_DATA_MODE={NEWS_DATA_MODE} PDF_DATA_MODE={PDF_DATA_MODE} PRICE_DATA_MODE={PRICE_DATA_MODE}")

    results: dict[str, bool] = {}
    for name, cfg in SERVERS.items():
        results[name] = await test_server(name, cfg)

    print(f"\n{'='*50}")
    print("RESULTS:")
    print(f"{'='*50}")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False

    print(f"\nOverall: {'ALL PASSED' if all_pass else 'SOME FAILED'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
