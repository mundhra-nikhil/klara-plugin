import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.department import Department
from src.models.enum.job_status import AuditAction, ActorType
from src.utils.audit_helpers import create_audit_log
from src.models.dto.schemas.responses import (
    DepartmentResponse,
    CreateDepartmentRequest,
)


async def list_departments(db: AsyncSession) -> List[DepartmentResponse]:
    stmt = select(Department).where(Department.is_active == True).order_by(Department.name)
    result = await db.execute(stmt)
    departments = result.scalars().all()
    return [DepartmentResponse.model_validate(d) for d in departments]


async def create_department(
    db: AsyncSession,
    body: CreateDepartmentRequest,
    actor_id: uuid.UUID,
) -> DepartmentResponse:
    stmt = select(Department).where(Department.name == body.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        from src.utils.dependencies import ConflictError
        raise ConflictError(f"Department '{body.name}' already exists")

    dept = Department(name=body.name, description=body.description)
    db.add(dept)
    await db.flush()

    await create_audit_log(
        db,
        entity_type="departments",
        entity_id=dept.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={"name": body.name},
    )

    return DepartmentResponse.model_validate(dept)
