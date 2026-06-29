from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ClientResponse(BaseModel):
    id: UUID
    name: str
    code: str
    is_active: bool
    qa_rule_profile: Optional[dict]
    blob_container_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateClientRequest(BaseModel):
    name: str
    code: str
    blob_container_name: str
    qa_rule_profile: Optional[dict] = None


class UpdateClientRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    qa_rule_profile: Optional[dict] = None
