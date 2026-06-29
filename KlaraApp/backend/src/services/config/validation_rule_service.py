import uuid
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.validation_rule import ClientValidationRule
from src.models.enum.job_status import AuditAction, ActorType
from src.utils.audit_helpers import create_audit_log
from src.repositories import validation_rule_repo
from src.models.dto.schemas.responses import (
    ValidationRuleResponse,
    CreateValidationRuleRequest,
    UpdateValidationRuleRequest,
)


async def list_validation_rules(
    db: AsyncSession,
    client_id: Optional[uuid.UUID] = None,
) -> List[ValidationRuleResponse]:
    rules = await validation_rule_repo.find_all(db, client_id=client_id)
    return [ValidationRuleResponse.model_validate(r) for r in rules]


async def create_validation_rule(
    db: AsyncSession,
    body: CreateValidationRuleRequest,
    actor_id: uuid.UUID,
) -> ValidationRuleResponse:
    rule = ClientValidationRule(
        client_id=body.client_id,
        name=body.name,
        rules=body.rules,
    )
    await validation_rule_repo.create(db, rule)

    await create_audit_log(
        db,
        entity_type="client_validation_rules",
        entity_id=rule.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={"name": body.name, "client_id": str(body.client_id)},
    )

    return ValidationRuleResponse.model_validate(rule)


async def update_validation_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
    body: UpdateValidationRuleRequest,
    actor_id: uuid.UUID,
) -> ValidationRuleResponse:
    rule = await validation_rule_repo.find_by_id(db, rule_id)
    if not rule:
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Validation rule {rule_id} not found")

    old_values = {}
    new_values = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        old_val = getattr(rule, field)
        old_values[field] = old_val
        new_values[field] = value
        setattr(rule, field, value)

    if new_values:
        await create_audit_log(
            db,
            entity_type="client_validation_rules",
            entity_id=rule.id,
            action=AuditAction.UPDATE,
            actor_id=actor_id,
            actor_type=ActorType.HUMAN,
            old_values=old_values,
            new_values=new_values,
        )

    await db.flush()
    # Refresh before serializing: updated_at is server-side (onupdate=func.now())
    # so a flushed change expires it, and model_validate would otherwise trigger
    # lazy IO outside the async greenlet (MissingGreenlet -> 500).
    await db.refresh(rule)
    return ValidationRuleResponse.model_validate(rule)
