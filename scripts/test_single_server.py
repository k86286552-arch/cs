"""Test a single MCP server via stdio."""
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_lme_price():
    print("=== Testing lme-price-mcp ===")
    env = {**os.environ, "APP_ENV": "development", "PRICE_DATA_MODE": "fixture"}
    env.pop("VIRTUAL_ENV", None)
    params = StdioServerParameters(
        command="uv",
        args=["--directory", r"D:\mineral-daily-agent\mcp_servers\lme_price", "run", "python", "-m", "app.server"],
        env=env,
    )
    async with stdio_client(params) as transport:
        read_stream, write_stream = transport
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("[OK] Connected")

            tools = await session.list_tools()
            print(f"[OK] Tools: {[t.name for t in tools.tools]}")

            result = await session.call_tool("get_price", {"commodity": "lithium_carbonate", "date": "2026-06-22"})
            data = json.loads(result.content[0].text)
            print(f"[OK] get_price: price={data.get('price')} {data.get('currency')}/{data.get('unit')}")

            result2 = await session.call_tool("get_trend", {"commodity": "lithium_carbonate", "days": 7})
            data2 = json.loads(result2.content[0].text)
            print(f"[OK] get_trend: change={data2.get('change_percent')}% points={len(data2.get('points', []))}")


async def test_mining_news():
    print("\n=== Testing mining-news-mcp ===")
    env = {**os.environ, "APP_ENV": "development", "NEWS_DATA_MODE": "fixture"}
    env.pop("VIRTUAL_ENV", None)
    params = StdioServerParameters(
        command="uv",
        args=["--directory", r"D:\mineral-daily-agent\mcp_servers\mining_news", "run", "python", "-m", "app.server"],
        env=env,
    )
    async with stdio_client(params) as transport:
        read_stream, write_stream = transport
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("[OK] Connected")

            tools = await session.list_tools()
            print(f"[OK] Tools: {[t.name for t in tools.tools]}")

            result = await session.call_tool("search", {"query": "Pilbara Minerals lithium", "days": 1, "limit": 5})
            data = json.loads(result.content[0].text)
            print(f"[OK] search: total={data.get('total')} items={len(data.get('items', []))}")
            for item in data.get("items", [])[:2]:
                print(f"     - {item.get('title', '')[:60]}")

            if data.get("items"):
                url = data["items"][0].get("url", "")
                result2 = await session.call_tool("fetch_article", {"url": url})
                data2 = json.loads(result2.content[0].text)
                print(f"[OK] fetch_article: title={data2.get('title', '')[:50]} parser={data2.get('parser')}")


async def test_mineral_pdf():
    print("\n=== Testing mineral-pdf-mcp ===")
    env = {**os.environ, "APP_ENV": "development", "PDF_DATA_MODE": "fixture"}
    env.pop("VIRTUAL_ENV", None)
    params = StdioServerParameters(
        command="uv",
        args=["--directory", r"D:\mineral-daily-agent\mcp_servers\mineral_pdf", "run", "python", "-m", "app.server"],
        env=env,
    )
    async with stdio_client(params) as transport:
        read_stream, write_stream = transport
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("[OK] Connected")

            tools = await session.list_tools()
            print(f"[OK] Tools: {[t.name for t in tools.tools]}")

            result = await session.call_tool("extract_resources", {
                "pdf_url": "https://pilbaraminerals.com.au/wp-content/uploads/2025/12/pilgangoora-ni43101.pdf",
                "project_hint": "Pilgangoora",
            })
            data = json.loads(result.content[0].text)
            print(f"[OK] extract_resources: status={data.get('status')} rows={len(data.get('resources', []))}")
            for row in data.get("resources", [])[:2]:
                print(f"     - {row.get('category')}: {row.get('ore_tonnage')} {row.get('ore_tonnage_unit')} @ {row.get('grade')} {row.get('grade_unit')}")


async def main():
    await test_lme_price()
    await test_mining_news()
    await test_mineral_pdf()
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
