from uuid import UUID
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.dao.qc_review import QCReview


async def find_by_id(db: AsyncSession, review_id: UUID) -> Optional[QCReview]:
    return await db.get(QCReview, review_id)


async def create(db: AsyncSession, review: QCReview) -> QCReview:
    db.add(review)
    await db.flush()
    return review


async def find_all(db: AsyncSession, document_id: Optional[UUID] = None) -> List[QCReview]:
    stmt = select(QCReview)
    if document_id:
        stmt = stmt.where(QCReview.document_id == document_id)
    stmt = stmt.order_by(QCReview.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
