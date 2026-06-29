from uuid import UUID
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.qc_finding import QCFinding


async def find_by_document_id(db: AsyncSession, document_id: UUID) -> List[QCFinding]:
    stmt = (
        select(QCFinding)
        .where(QCFinding.document_id == document_id)
        .order_by(QCFinding.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def find_by_id(db: AsyncSession, finding_id: UUID) -> Optional[QCFinding]:
    return await db.get(QCFinding, finding_id)


async def create(db: AsyncSession, finding: QCFinding) -> QCFinding:
    db.add(finding)
    await db.flush()
    return finding
