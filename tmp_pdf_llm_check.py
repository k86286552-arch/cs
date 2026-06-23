import asyncio
from app.providers.llm_structurer import structure_with_llm

async def main():
    rows = await structure_with_llm([
        {
            'page_number': 1,
            'text': 'Indicated Mineral Resources: 120.5 Mt at 1.21% Li2O. Inferred Mineral Resources: 46.2 Mt at 1.08% Li2O.'
        }
    ])
    print('rows_count=' + str(len(rows)))
    print(rows[:2])

asyncio.run(main())
