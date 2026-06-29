import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.user import User
from src.models.enum.job_status import AuditAction, ActorType
from src.utils.audit_helpers import create_audit_log
from src.repositories import user_repo
from src.models.dto.schemas.users import (
    UserResponse,
    CreateUserRequest,
    UpdateUserRequest,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def list_users(
    db: AsyncSession,
    *,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    logger.info("Entering list_users", function="list_users", action="entry", is_active=is_active, limit=limit, offset=offset)
    users, total = await user_repo.find_all(db, is_active=is_active, limit=limit, offset=offset)
    logger.info("Exiting list_users", function="list_users", action="exit", user_count=len(users), total=total)
    return {
        "data": [UserResponse.model_validate(u) for u in users],
        "total": total,
    }


async def create_user(
    db: AsyncSession,
    body: CreateUserRequest,
    actor_id: uuid.UUID,
) -> UserResponse:
    logger.info("Entering create_user", function="create_user", action="entry", email=body.email, role=body.role.value, actor_id=str(actor_id))
    
    logger.info("Checking for existing user", function="create_user", step="check_existing")
    existing = await user_repo.find_by_email_or_oid(db, body.email, body.azure_ad_oid)
    if existing:
        logger.warning("User already exists", function="create_user", email=body.email)
        from src.utils.dependencies import ConflictError
        raise ConflictError("User with this Azure AD OID or email already exists")

    logger.info("Creating new user", function="create_user", step="create_user")
    user = User(
        azure_ad_oid=body.azure_ad_oid,
        email=body.email,
        display_name=body.display_name,
        department_id=body.department_id,
        role=body.role,
    )
    await user_repo.create(db, user)
    logger.info("User created", function="create_user", step="user_created", user_id=str(user.id))

    logger.info("Creating audit log", function="create_user", step="audit_log")
    await create_audit_log(
        db,
        entity_type="users",
        entity_id=user.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={"email": body.email, "role": body.role.value},
    )

    logger.info("Exiting create_user", function="create_user", action="exit", user_id=str(user.id))
    return UserResponse.model_validate(user)


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    actor_id: uuid.UUID,
) -> UserResponse:
    user = await user_repo.find_by_id(db, user_id)
    if not user:
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"User {user_id} not found")

    old_values = {}
    new_values = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        old_values[field] = getattr(user, field)
        if isinstance(old_values[field], uuid.UUID):
            old_values[field] = str(old_values[field])
        new_values[field] = value
        if isinstance(value, uuid.UUID):
            new_values[field] = str(value)
        setattr(user, field, value)

    if new_values:
        await create_audit_log(
            db,
            entity_type="users",
            entity_id=user.id,
            action=AuditAction.UPDATE,
            actor_id=actor_id,
            actor_type=ActorType.HUMAN,
            old_values=old_values,
            new_values=new_values,
        )

    await db.flush()
    return UserResponse.model_validate(user)
