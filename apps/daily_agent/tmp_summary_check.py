import asyncio
from dotenv import load_dotenv
from app.agent.nodes.compose_report import _generate_summary

load_dotenv('D:/mineral-daily-agent/.env')

async def main():
    evidence = [
        {
            'evidence_id': 'N1',
            'evidence_type': 'news',
            'title': 'Pilbara Minerals updates FY26 production guidance',
            'content': 'Pilbara Minerals raised production guidance by about 5% for the Pilgangoora operation.',
        },
        {
            'evidence_id': 'P1',
            'evidence_type': 'price',
            'title': 'lithium_carbonate price on 2026-06-23',
            'content': '97500 CNY/tonne',
        },
    ]
    risks = [
        {
            'description': 'Price data is sourced from demo fixtures, not live market data.',
            'severity': 'low',
        }
    ]
    summary = await _generate_summary(evidence, risks)
    print(repr(summary))

asyncio.run(main())
