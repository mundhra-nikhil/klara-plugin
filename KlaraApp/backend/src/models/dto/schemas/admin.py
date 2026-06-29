from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from src.models.enum.job_status import AuditAction, ActorType


class AuditLogResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: UUID
    action: AuditAction
    actor_id: Optional[UUID]
    actor_type: ActorType
    old_values: Optional[dict]
    new_values: Optional[dict]
    ip_address: Optional[str]
    correlation_id: Optional[UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    data: List[AuditLogResponse]
    next_cursor: Optional[str] = None
    total: int


class SystemConfigResponse(BaseModel):
    id: UUID
    key: str
    value: dict
    description: Optional[str]
    ttl_seconds: Optional[int]
    updated_at: datetime

    model_config = {"from_attributes": True}
