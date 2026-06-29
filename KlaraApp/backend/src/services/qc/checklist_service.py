from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enum.document_type import DocumentType
from src.repositories import checklist_repo
from src.models.dto.schemas.qc import ChecklistResponse


async def list_checklists(
    db: AsyncSession,
    document_type: Optional[DocumentType] = None,
) -> List[ChecklistResponse]:
    checklists = await checklist_repo.find_all(db, document_type=document_type)
    return [ChecklistResponse.model_validate(c) for c in checklists]
