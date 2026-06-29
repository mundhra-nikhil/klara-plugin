from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.document import Document
from src.models.dao.qc_finding import QCFinding
from src.models.dto.schemas.responses import ComplianceReportResponse


async def get_compliance_report(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> ComplianceReportResponse:
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    # Documents by status
    doc_status_query = (
        select(Document.status, func.count(Document.id))
        .where(Document.created_at.between(start_date, end_date))
        .where(Document.deleted_at == None)
        .group_by(Document.status)
    )
    doc_result = await db.execute(doc_status_query)
    documents_by_status = {str(row[0].value): row[1] for row in doc_result.all()}
    total_documents = sum(documents_by_status.values())

    # Findings by severity
    sev_query = (
        select(QCFinding.severity, func.count(QCFinding.id))
        .where(QCFinding.created_at.between(start_date, end_date))
        .group_by(QCFinding.severity)
    )
    sev_result = await db.execute(sev_query)
    findings_by_severity = {str(row[0].value): row[1] for row in sev_result.all()}

    # Findings by type
    type_query = (
        select(QCFinding.finding_type, func.count(QCFinding.id))
        .where(QCFinding.created_at.between(start_date, end_date))
        .group_by(QCFinding.finding_type)
    )
    type_result = await db.execute(type_query)
    findings_by_type = {str(row[0].value): row[1] for row in type_result.all()}

    total_findings = sum(findings_by_severity.values())

    # Resolution rate
    resolved_query = (
        select(func.count(QCFinding.id))
        .where(QCFinding.created_at.between(start_date, end_date))
        .where(QCFinding.resolved_at != None)
    )
    resolved_result = await db.execute(resolved_query)
    resolved_count = resolved_result.scalar() or 0
    resolution_rate = (resolved_count / total_findings * 100) if total_findings > 0 else 0.0

    # Avg resolution time
    avg_time_query = (
        select(
            func.avg(
                extract("epoch", QCFinding.resolved_at - QCFinding.created_at) / 3600
            )
        )
        .where(QCFinding.created_at.between(start_date, end_date))
        .where(QCFinding.resolved_at != None)
    )
    avg_result = await db.execute(avg_time_query)
    avg_resolution_time = avg_result.scalar()

    return ComplianceReportResponse(
        period_start=start_date,
        period_end=end_date,
        total_documents=total_documents,
        documents_by_status=documents_by_status,
        total_findings=total_findings,
        findings_by_severity=findings_by_severity,
        findings_by_type=findings_by_type,
        resolution_rate=round(resolution_rate, 2),
        avg_resolution_time_hours=round(avg_resolution_time, 2) if avg_resolution_time else None,
    )
