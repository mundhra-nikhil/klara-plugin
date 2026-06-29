from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.document import Document
from src.models.enum.document_status import DocumentStatus
from src.models.dto.schemas.responses import ThroughputReportResponse


async def get_throughput_report(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ThroughputReportResponse:
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    # Total completed
    completed_query = (
        select(func.count(Document.id))
        .where(Document.created_at.between(start_date, end_date))
        .where(Document.status == DocumentStatus.COMPLETED)
        .where(Document.deleted_at == None)
    )
    completed_result = await db.execute(completed_query)
    total_processed = completed_result.scalar() or 0

    # Per-day breakdown
    daily_query = (
        select(
            func.date_trunc("day", Document.created_at).label("day"),
            func.count(Document.id),
        )
        .where(Document.created_at.between(start_date, end_date))
        .where(Document.deleted_at == None)
        .group_by("day")
        .order_by("day")
    )
    daily_result = await db.execute(daily_query)
    documents_per_day = [
        {"date": row[0].isoformat(), "count": row[1]} for row in daily_result.all()
    ]

    # By type
    type_query = (
        select(Document.document_type, func.count(Document.id))
        .where(Document.created_at.between(start_date, end_date))
        .where(Document.deleted_at == None)
        .group_by(Document.document_type)
    )
    type_result = await db.execute(type_query)
    documents_by_type = {str(row[0].value): row[1] for row in type_result.all()}

    # By priority
    priority_query = (
        select(Document.priority, func.count(Document.id))
        .where(Document.created_at.between(start_date, end_date))
        .where(Document.deleted_at == None)
        .group_by(Document.priority)
    )
    priority_result = await db.execute(priority_query)
    documents_by_priority = {str(row[0]): row[1] for row in priority_result.all()}

    return ThroughputReportResponse(
        period_start=start_date,
        period_end=end_date,
        total_documents_processed=total_processed,
        documents_per_day=documents_per_day,
        avg_processing_time_hours=None,
        documents_by_type=documents_by_type,
        documents_by_priority=documents_by_priority,
    )
