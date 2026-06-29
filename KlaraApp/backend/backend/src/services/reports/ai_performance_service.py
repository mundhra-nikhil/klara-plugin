from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.ai_analysis_job import AIAnalysisJob
from src.models.dao.qc_finding import QCFinding
from src.models.enum.job_status import AIJobStatus
from src.models.dto.schemas.responses import AIPerformanceReportResponse


async def get_ai_performance_report(
    db: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> AIPerformanceReportResponse:
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    # Jobs by status
    status_query = (
        select(AIAnalysisJob.status, func.count(AIAnalysisJob.id))
        .where(AIAnalysisJob.created_at.between(start_date, end_date))
        .group_by(AIAnalysisJob.status)
    )
    status_result = await db.execute(status_query)
    jobs_by_status = {str(row[0].value): row[1] for row in status_result.all()}
    total_jobs = sum(jobs_by_status.values())

    # Jobs by type
    type_query = (
        select(AIAnalysisJob.job_type, func.count(AIAnalysisJob.id))
        .where(AIAnalysisJob.created_at.between(start_date, end_date))
        .group_by(AIAnalysisJob.job_type)
    )
    type_result = await db.execute(type_query)
    jobs_by_type = {str(row[0].value): row[1] for row in type_result.all()}

    # Latency stats
    latency_query = (
        select(
            func.avg(extract("epoch", AIAnalysisJob.completed_at - AIAnalysisJob.started_at)),
            func.percentile_cont(0.95).within_group(
                extract("epoch", AIAnalysisJob.completed_at - AIAnalysisJob.started_at)
            ),
        )
        .where(AIAnalysisJob.created_at.between(start_date, end_date))
        .where(AIAnalysisJob.status == AIJobStatus.COMPLETED)
        .where(AIAnalysisJob.started_at != None)
        .where(AIAnalysisJob.completed_at != None)
    )
    latency_result = await db.execute(latency_query)
    latency_row = latency_result.one_or_none()
    avg_latency = latency_row[0] if latency_row else None
    p95_latency = latency_row[1] if latency_row else None

    # Token usage
    token_query = (
        select(
            func.coalesce(func.sum(AIAnalysisJob.prompt_tokens), 0),
            func.coalesce(func.sum(AIAnalysisJob.completion_tokens), 0),
        )
        .where(AIAnalysisJob.created_at.between(start_date, end_date))
    )
    token_result = await db.execute(token_query)
    token_row = token_result.one()

    # Avg findings per completed job
    completed_count = jobs_by_status.get("completed", 0)
    findings_count_query = (
        select(func.count(QCFinding.id))
        .join(AIAnalysisJob, QCFinding.analysis_job_id == AIAnalysisJob.id)
        .where(AIAnalysisJob.created_at.between(start_date, end_date))
        .where(AIAnalysisJob.status == AIJobStatus.COMPLETED)
    )
    findings_result = await db.execute(findings_count_query)
    total_findings = findings_result.scalar() or 0
    avg_findings = (total_findings / completed_count) if completed_count > 0 else 0.0

    return AIPerformanceReportResponse(
        period_start=start_date,
        period_end=end_date,
        total_jobs=total_jobs,
        jobs_by_status=jobs_by_status,
        jobs_by_type=jobs_by_type,
        avg_latency_seconds=round(avg_latency, 2) if avg_latency else None,
        p95_latency_seconds=round(p95_latency, 2) if p95_latency else None,
        total_prompt_tokens=token_row[0],
        total_completion_tokens=token_row[1],
        avg_findings_per_job=round(avg_findings, 2),
    )
