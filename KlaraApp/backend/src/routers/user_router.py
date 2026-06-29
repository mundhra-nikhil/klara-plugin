from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.repositories.db_setup import get_db
from src.utils.dependencies import require_roles
from src.models.enum.user_role import UserRole
from src.models.dao.user import User
from src.services.users import user_mgmt_service
from src.models.dto.schemas.users import (
    UserResponse,
    StaffResponse,
    CreateUserRequest,
    UpdateUserRequest,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.get("", response_model=dict)
async def list_users(
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(require_roles([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    logger.info("Entering list_users", function="list_users", action="entry", is_active=is_active, limit=limit, offset=offset)
    result = await user_mgmt_service.list_users(db, is_active=is_active, limit=limit, offset=offset)
    logger.info("Exiting list_users", function="list_users", action="exit", user_count=len(result.get("data", [])))
    return result


@router.get("/staff", response_model=List[StaffResponse])
async def list_assignable_staff(
    role: Optional[UserRole] = Query(None, description="Filter by role: doc_specialist or qc_operator"),
    is_active: Optional[bool] = Query(True),
    current_user=Depends(require_roles([
        UserRole.INTAKE_COORDINATOR,
        UserRole.MANAGER,
        UserRole.ADMIN,
    ])),
    db: AsyncSession = Depends(get_db),
):
    """List assignable staff (doc_specialists and qc_operators) for manual job routing.

    Accessible by Intake Coordinators, Managers, and Admins.
    """
    logger.info(
        "Entering list_assignable_staff",
        function="list_assignable_staff",
        action="entry",
        role=role.value if role else None,
        is_active=is_active,
        user_id=str(current_user.id),
    )

    # Only allow fetching doc_specialist, qc_operator, and proofreader roles
    allowed_roles = [UserRole.DOC_SPECIALIST, UserRole.QC_OPERATOR, UserRole.PROOFREADER]
    if role is not None:
        if role not in allowed_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Role filter must be one of: {[r.value for r in allowed_roles]}"
            )
        filter_roles = [role]
    else:
        filter_roles = allowed_roles

    query = select(User).where(User.role.in_(filter_roles))
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    query = query.order_by(User.display_name)

    result = await db.execute(query)
    staff = list(result.scalars().all())

    logger.info(
        "Exiting list_assignable_staff",
        function="list_assignable_staff",
        action="exit",
        staff_count=len(staff),
    )
    return [StaffResponse.model_validate(u) for u in staff]


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    current_user=Depends(require_roles([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only)."""
    logger.info("Entering create_user", function="create_user", action="entry", email=body.email, role=body.role)
    result = await user_mgmt_service.create_user(db, body, actor_id=current_user.id)
    logger.info("Exiting create_user", function="create_user", action="exit", user_id=str(result.id))
    return result


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UpdateUserRequest,
    current_user=Depends(require_roles([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Update user details (admin only)."""
    logger.info("Entering update_user", function="update_user", action="entry", user_id=str(user_id))
    result = await user_mgmt_service.update_user(db, user_id, body, actor_id=current_user.id)
    logger.info("Exiting update_user", function="update_user", action="exit", user_id=str(user_id))
    return result
