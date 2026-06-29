from uuid import UUID
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.audit_log import AuditLog
from src.models.enum.job_status import AuditAction, ActorType
from datetime import datetime


async def create(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: UUID,
    action: AuditAction,
    actor_id: UUID | None = None,
    actor_type: ActorType = ActorType.HUMAN,
    old_values: dict | None = None,
    new_values: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    correlation_id: UUID | None = None,
) -> AuditLog:
    log_entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_type=actor_type,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id,
    )
    db.add(log_entry)
    await db.flush()
    return log_entry


async def find_all(
    db: AsyncSession,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    actor_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
) -> tuple[list, Optional[str], int]:
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
        count_query = count_query.where(AuditLog.entity_id == entity_id)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
        count_query = count_query.where(AuditLog.actor_id == actor_id)
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
        count_query = count_query.where(AuditLog.created_at >= start_date)
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
        count_query = count_query.where(AuditLog.created_at <= end_date)
    if cursor:
        query = query.where(AuditLog.id < int(cursor))

    query = query.order_by(AuditLog.id.desc()).limit(limit + 1)

    result = await db.execute(query)
    logs = list(result.scalars().all())
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    next_cursor = None
    if len(logs) > limit:
        logs = logs[:limit]
        next_cursor = str(logs[-1].id)

    return logs, next_cursor, total
