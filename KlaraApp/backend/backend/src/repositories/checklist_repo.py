from uuid import UUID
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload
from src.models.dao.checklist import QCChecklist
from src.models.enum.document_type import DocumentType


async def find_all(
    db: AsyncSession,
    document_type: Optional[DocumentType] = None,
) -> List[QCChecklist]:
    stmt = select(QCChecklist).options(selectinload(QCChecklist.items)).where(QCChecklist.is_active == True)
    if document_type:
        stmt = stmt.where(QCChecklist.document_type == document_type)
    stmt = stmt.order_by(QCChecklist.name)

    result = await db.execute(stmt)
    return list(result.scalars().all())
