from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    project_root = Path(__file__).resolve().parents[3]
    load_dotenv(project_root / ".env")

    if len(sys.argv) < 2:
        query = "给我生成一份关于 Pilbara 锂矿的今日简报"
        print(f"未提供查询参数，使用默认: {query}", file=sys.stderr)
    else:
        query = " ".join(sys.argv[1:])

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Mining Daily Brief Agent", file=sys.stderr)
    print(f"Query: {query}", file=sys.stderr)
    print(f"Date: {date.today().isoformat()}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    result = asyncio.run(_run(query))

    print(result["markdown"])

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Request ID: {result.get('request_id', 'N/A')}", file=sys.stderr)
    print(f"Status: {result.get('status', 'N/A')}", file=sys.stderr)
    print(f"Tool Status: {result.get('tool_status', {})}", file=sys.stderr)
    if result.get("warnings"):
        print(f"Warnings: {len(result['warnings'])}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    output_dir = project_root / "data" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"brief_{timestamp}.md"
    output_path.write_text(result["markdown"], encoding="utf-8")
    print(f"\nReport saved to: {output_path}", file=sys.stderr)


async def _run(query: str) -> dict:
    from app.agent.graph import DailyBriefAgent

    agent = DailyBriefAgent()
    return await agent.run(query)


if __name__ == "__main__":
    main()
