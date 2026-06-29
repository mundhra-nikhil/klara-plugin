import asyncio
import uuid
from src.repositories.db_setup import AsyncSessionLocal
from src.models.dao.qc_finding import QCFinding
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(QCFinding).where(QCFinding.document_id == uuid.UUID("11111111-1111-1111-1111-111111111111")))
        findings = res.scalars().all()
        print(f"Total findings: {len(findings)}")
        for f in findings:
            print(f"- {f.id}: {f.description} (status: {f.status})")

if __name__ == '__main__':
    asyncio.run(main())
