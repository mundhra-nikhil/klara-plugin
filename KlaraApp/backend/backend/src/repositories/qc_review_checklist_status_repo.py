from uuid import UUID
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dao.qc_review_checklist_status import QCReviewChecklistStatus


async def save_status(
    db: AsyncSession,
    review_id: UUID,
    checklist_item_id: UUID,
    status: str,
    details: Optional[str] = None
) -> QCReviewChecklistStatus:
    # Check if a status already exists
    stmt = select(QCReviewChecklistStatus).where(
        QCReviewChecklistStatus.review_id == review_id,
        QCReviewChecklistStatus.checklist_item_id == checklist_item_id
    )
    result = await db.execute(stmt)
    db_status = result.scalar_one_or_none()

    if db_status:
        db_status.status = status
        if details is not None:
            db_status.details = details
    else:
        db_status = QCReviewChecklistStatus(
            review_id=review_id,
            checklist_item_id=checklist_item_id,
            status=status,
            details=details or ""
        )
        db.add(db_status)

    await db.flush()
    return db_status


async def get_statuses_for_review(
    db: AsyncSession,
    review_id: UUID
) -> List[QCReviewChecklistStatus]:
    stmt = select(QCReviewChecklistStatus).where(QCReviewChecklistStatus.review_id == review_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
