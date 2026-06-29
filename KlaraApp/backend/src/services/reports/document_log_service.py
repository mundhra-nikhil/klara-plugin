"""List Report — per-document review metrics.

Powers the "Reports" list view. Each row carries the submission and completion
dates, the wall-clock turnaround between them, and the level of effort (LOE) —
defined as the summed duration of the document's completed QC review sessions.
LOE is None for documents that never went through a QC review session.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.document import Document
from src.models.dao.client import Client
from src.models.dao.user import User
from src.models.dao.qc_review import QCReview
from src.models.enum.document_status import DocumentStatus
from src.models.dto.schemas.responses import DocumentLogResponse, DocumentLogEntry
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


def _to_minutes(seconds: Optional[float]) -> Optional[int]:
    if seconds is None:
        return None
    return max(0, int(round(seconds / 60.0)))


async def get_document_log(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[DocumentStatus] = None,
    limit: int = 200,
) -> DocumentLogResponse:
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    submitted = func.coalesce(Document.submitted_at, Document.created_at)

    # Per-document LOE: sum of completed QC review session durations (seconds).
    loe_subq = (
        select(
            QCReview.document_id.label("doc_id"),
            func.sum(
                func.extract("epoch", QCReview.completed_at - QCReview.started_at)
            ).label("loe_seconds"),
        )
        .where(QCReview.completed_at.isnot(None))
        .where(QCReview.started_at.isnot(None))
        .group_by(QCReview.document_id)
        .subquery()
    )

    base_filters = [Document.deleted_at.is_(None), submitted.between(start_date, end_date)]
    if status is not None:
        base_filters.append(Document.status == status)

    from sqlalchemy.orm import selectinload
    query = (
        select(Document, Client.name, User.display_name, loe_subq.c.loe_seconds)
        .outerjoin(Client, Client.id == Document.client_id)
        .outerjoin(User, User.id == Document.assigned_specialist_id)
        .outerjoin(loe_subq, loe_subq.c.doc_id == Document.id)
        .options(selectinload(Document.ai_analysis_jobs))
        .where(*base_filters)
        .order_by(submitted.desc())
        .limit(limit)
    )

    count_query = (
        select(func.count()).select_from(Document).where(*base_filters)
    )

    rows = (await db.execute(query)).all()
    total = (await db.execute(count_query)).scalar() or 0

    items: list[DocumentLogEntry] = []
    for doc, client_name, specialist_name, loe_seconds in rows:
        sub_at = doc.submitted_at or doc.created_at
        comp_at = doc.completed_at
        turnaround = None
        if comp_at and sub_at:
            turnaround = _to_minutes((comp_at - sub_at).total_seconds())
        items.append(
            DocumentLogEntry(
                document_id=doc.id,
                title=doc.title,
                client_name=client_name,
                document_type=getattr(doc.document_type, "value", str(doc.document_type)),
                status=getattr(doc.status, "value", str(doc.status)),
                validation_mode=doc.validation_mode or "auto",
                ai_status=doc.ai_status,
                assigned_specialist_name=specialist_name,
                submitted_at=sub_at,
                completed_at=comp_at,
                turnaround_minutes=turnaround,
                loe_minutes=_to_minutes(float(loe_seconds) if loe_seconds is not None else None),
            )
        )

    return DocumentLogResponse(
        period_start=start_date,
        period_end=end_date,
        total=total,
        items=items,
    )
