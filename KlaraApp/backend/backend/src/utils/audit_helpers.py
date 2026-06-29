"""Audit log write helpers."""

from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.audit_log import AuditLog
from src.models.enum.job_status import AuditAction, ActorType
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def create_audit_log(
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
):
    logger.info("Entering create_audit_log", function="create_audit_log", action="entry", entity_type=entity_type, entity_id=str(entity_id), audit_action=action.value)
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
    logger.info("Exiting create_audit_log", function="create_audit_log", action="exit", audit_log_id=str(log_entry.id))
    return log_entry
