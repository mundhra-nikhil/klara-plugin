from uuid import UUID
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.validation_rule import ClientValidationRule


async def find_all(
    db: AsyncSession,
    client_id: Optional[UUID] = None,
) -> List[ClientValidationRule]:
    stmt = select(ClientValidationRule)
    if client_id:
        stmt = stmt.where(ClientValidationRule.client_id == client_id)
    stmt = stmt.order_by(ClientValidationRule.name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def find_by_id(db: AsyncSession, rule_id: UUID) -> Optional[ClientValidationRule]:
    return await db.get(ClientValidationRule, rule_id)


async def create(db: AsyncSession, rule: ClientValidationRule) -> ClientValidationRule:
    db.add(rule)
    await db.flush()
    return rule
