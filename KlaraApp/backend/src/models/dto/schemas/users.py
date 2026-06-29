from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

from src.models.enum.user_role import UserRole


class UserResponse(BaseModel):
    id: UUID
    azure_ad_oid: Optional[str] = None  # nullable for password-auth users
    email: str
    display_name: str
    department_id: Optional[UUID] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StaffResponse(BaseModel):
    """Lean response used by the /staff listing endpoint."""
    id: UUID
    email: str
    display_name: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    azure_ad_oid: str
    email: EmailStr
    display_name: str
    department_id: Optional[UUID] = None
    role: UserRole


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    department_id: Optional[UUID] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
