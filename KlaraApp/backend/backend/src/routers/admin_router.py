from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import require_roles
from src.models.enum.user_role import UserRole
from src.services.auth import auth_service
from src.models.dto.schemas.admin import AuditLogListResponse
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.get("/audit-log", response_model=AuditLogListResponse)
async def get_audit_log(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[UUID] = Query(None),
    actor_id: Optional[UUID] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_roles([UserRole.ADMIN, UserRole.INTAKE_COORDINATOR, UserRole.QC_OPERATOR, UserRole.MANAGER])),
    db: AsyncSession = Depends(get_db),
):
    """Query the immutable audit log (admin only)."""
    logger.info("Entering get_audit_log", function="get_audit_log", action="entry", entity_type=entity_type, entity_id=str(entity_id) if entity_id else None, actor_id=str(actor_id) if actor_id else None, limit=limit)
    from src.repositories import audit_log_repo
    from src.models.dto.schemas.admin import AuditLogResponse

    logs, next_cursor, total = await audit_log_repo.find_all(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        start_date=start_date,
        end_date=end_date,
        cursor=cursor,
        limit=limit,
    )

    logger.info("Exiting get_audit_log", function="get_audit_log", action="exit", log_count=len(logs), total=total)
    return {
        "data": [AuditLogResponse.model_validate(log) for log in logs],
        "next_cursor": next_cursor,
        "total": total,
    }
