import asyncio
from src.repositories.db_setup import AsyncSessionLocal
from src.models.dao.document import Document
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Document))
        docs = res.scalars().all()
        print(f"Total docs: {len(docs)}")
        for d in docs:
            print(f"- {d.id}: {d.title}")

if __name__ == '__main__':
    asyncio.run(main())
