from typing import Optional, Dict, Any
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SystemConfigResponse(BaseModel):
    id: UUID
    key: str
    value: Dict[str, Any]
    description: Optional[str] = None
    ttl_seconds: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class SetSystemConfigRequest(BaseModel):
    value: Dict[str, Any]
    description: Optional[str] = None
    ttl_seconds: Optional[int] = None
