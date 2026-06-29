from uuid import UUID
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.dao.document import Document
from src.models.dao.document import DocumentVersion
from src.models.enum.document_status import DocumentStatus
from src.models.enum.document_type import DocumentType
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def find_all(
    db: AsyncSession,
    *,
    client_id: Optional[UUID] = None,
    status: Optional[DocumentStatus] = None,
    document_type: Optional[DocumentType] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
    assigned_specialist_id: Optional[UUID] = None,
) -> tuple[List[Document], Optional[str], int]:
    logger.info("Entering find_all", function="find_all", action="entry", client_id=str(client_id) if client_id else None, status=status, document_type=document_type, limit=limit)
    query = select(Document).options(selectinload(Document.ai_analysis_jobs)).where(Document.deleted_at == None)

    if client_id:
        query = query.where(Document.client_id == client_id)
    if status:
        query = query.where(Document.status == status)
    if document_type:
        query = query.where(Document.document_type == document_type)
    if assigned_specialist_id:
        query = query.where(Document.assigned_specialist_id == assigned_specialist_id)
    if cursor:
        query = query.where(Document.created_at < datetime.fromisoformat(cursor))

    query = query.order_by(Document.created_at.desc()).limit(limit + 1)

    count_query = select(func.count()).select_from(Document).where(Document.deleted_at == None)
    if client_id:
        count_query = count_query.where(Document.client_id == client_id)
    if assigned_specialist_id:
        count_query = count_query.where(Document.assigned_specialist_id == assigned_specialist_id)

    logger.info("Executing database queries", function="find_all", step="execute_queries")
    result = await db.execute(query)
    documents = list(result.scalars().all())
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    next_cursor = None
    if len(documents) > limit:
        documents = documents[:limit]
        next_cursor = documents[-1].created_at.isoformat()

    logger.info("Exiting find_all", function="find_all", action="exit", document_count=len(documents), total=total)
    return documents, next_cursor, total


async def find_by_id(db: AsyncSession, document_id: UUID) -> Optional[Document]:
    logger.info("Entering find_by_id", function="find_by_id", action="entry", document_id=str(document_id))
    stmt = select(Document).options(selectinload(Document.ai_analysis_jobs)).where(Document.id == document_id, Document.deleted_at == None)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()
    logger.info("Exiting find_by_id", function="find_by_id", action="exit", document_id=str(document_id), found=document is not None)
    return document


async def create(db: AsyncSession, document: Document) -> Document:
    logger.info("Entering create", function="create", action="entry", document_id=str(document.id))
    db.add(document)
    await db.flush()
    logger.info("Exiting create", function="create", action="exit", document_id=str(document.id))
    return document


async def find_versions(db: AsyncSession, document_id: UUID) -> List:
    logger.info("Entering find_versions", function="find_versions", action="entry", document_id=str(document_id))
    from src.models.dao.document import Document as Doc
    stmt = (
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    result = await db.execute(stmt)
    versions = list(result.scalars().all())
    logger.info("Exiting find_versions", function="find_versions", action="exit", document_id=str(document_id), version_count=len(versions))
    return versions
