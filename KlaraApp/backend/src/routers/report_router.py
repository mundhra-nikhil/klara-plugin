from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import require_roles
from src.models.enum.user_role import UserRole
from src.models.enum.document_status import DocumentStatus
from src.services.reports import (
    compliance_report_service,
    throughput_report_service,
    ai_performance_service,
    document_log_service,
)
from src.models.dto.schemas.responses import (
    ComplianceReportResponse,
    AIPerformanceReportResponse,
    ThroughputReportResponse,
    DocumentLogResponse,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.get("/compliance", response_model=ComplianceReportResponse)
async def compliance_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user=Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Compliance audit report with filterable date range."""
    logger.info("Entering compliance_report", function="compliance_report", action="entry", start_date=start_date, end_date=end_date)
    result = await compliance_report_service.get_compliance_report(db, start_date, end_date)
    logger.info("Exiting compliance_report", function="compliance_report", action="exit")
    return result


@router.get("/ai-performance", response_model=AIPerformanceReportResponse)
async def ai_performance_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user=Depends(require_roles([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """AI accuracy, token usage, and latency metrics."""
    logger.info("Entering ai_performance_report", function="ai_performance_report", action="entry", start_date=start_date, end_date=end_date)
    result = await ai_performance_service.get_ai_performance_report(db, start_date, end_date)
    logger.info("Exiting ai_performance_report", function="ai_performance_report", action="exit")
    return result


@router.get("/documents", response_model=DocumentLogResponse)
async def document_log_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    status: Optional[DocumentStatus] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    current_user=Depends(require_roles([
        UserRole.INTAKE_COORDINATOR, UserRole.QC_OPERATOR,
        UserRole.MANAGER, UserRole.ADMIN,
    ])),
    db: AsyncSession = Depends(get_db),
):
    """List Report: per-document submission/completion dates, turnaround and LOE."""
    logger.info("Entering document_log_report", function="document_log_report", action="entry",
                start_date=start_date, end_date=end_date, status=status, limit=limit)
    result = await document_log_service.get_document_log(db, start_date, end_date, status, limit)
    logger.info("Exiting document_log_report", function="document_log_report", action="exit", total=result.total)
    return result


@router.get("/throughput", response_model=ThroughputReportResponse)
async def throughput_report(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user=Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Document processing throughput dashboard data."""
    logger.info("Entering throughput_report", function="throughput_report", action="entry", start_date=start_date, end_date=end_date)
    result = await throughput_report_service.get_throughput_report(db, start_date, end_date)
    logger.info("Exiting throughput_report", function="throughput_report", action="exit")
    return result
