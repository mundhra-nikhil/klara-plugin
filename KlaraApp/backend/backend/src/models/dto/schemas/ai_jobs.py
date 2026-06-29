from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

from src.models.enum.job_type import AIJobType
from src.models.enum.job_status import AIJobStatus


class CreateAIJobRequest(BaseModel):
    document_id: UUID
    job_type: AIJobType


class AIJobResponse(BaseModel):
    id: UUID
    document_id: UUID
    job_type: AIJobType
    status: AIJobStatus
    queue_job_id: Optional[str]
    model_used: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    results: Optional[dict]
    error_message: Optional[str]
    retry_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}
