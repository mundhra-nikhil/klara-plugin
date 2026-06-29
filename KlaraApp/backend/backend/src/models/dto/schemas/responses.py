from pydantic import BaseModel
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime

from src.models.dto.schemas.documents import DocumentResponse, DocumentVersionResponse
from src.models.dto.schemas.qc import FindingResponse, ReviewResponse, ChecklistResponse
from src.models.dto.schemas.ai_jobs import AIJobResponse
from src.models.dto.schemas.users import UserResponse
from src.models.dto.schemas.admin import AuditLogResponse


class PaginationParams(BaseModel):
    cursor: Optional[str] = None
    limit: int = 20


class PaginatedResponse(BaseModel):
    data: List[Any]
    next_cursor: Optional[str] = None
    total: Optional[int] = None


class ComplianceReportResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_documents: int
    documents_by_status: dict[str, int]
    total_findings: int
    findings_by_severity: dict[str, int]
    findings_by_type: dict[str, int]
    resolution_rate: float
    avg_resolution_time_hours: Optional[float]


class AIPerformanceReportResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_jobs: int
    jobs_by_status: dict[str, int]
    jobs_by_type: dict[str, int]
    avg_latency_seconds: Optional[float]
    p95_latency_seconds: Optional[float]
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_findings_per_job: float


class ThroughputReportResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_documents_processed: int
    documents_per_day: List[dict[str, Any]]
    avg_processing_time_hours: Optional[float]
    documents_by_type: dict[str, int]
    documents_by_priority: dict[str, int]


class DocumentLogEntry(BaseModel):
    """One row of the List Report view — per-document review metrics."""
    document_id: UUID
    title: str
    client_name: Optional[str] = None
    document_type: str
    status: str
    validation_mode: str = "auto"
    ai_status: Optional[str] = "not_started"
    assigned_specialist_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # Wall-clock from submission to completion, in whole minutes (None until done).
    turnaround_minutes: Optional[int] = None
    # Level of effort = summed QC-review session duration, in whole minutes
    # (None when the document never went through a QC review session).
    loe_minutes: Optional[int] = None


class DocumentLogResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total: int
    items: List[DocumentLogEntry]


class ValidationRuleResponse(BaseModel):
    id: UUID
    client_id: UUID
    name: str
    rules: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateValidationRuleRequest(BaseModel):
    client_id: UUID
    name: str
    rules: dict


class UpdateValidationRuleRequest(BaseModel):
    name: Optional[str] = None
    rules: Optional[dict] = None
    is_active: Optional[bool] = None


class DepartmentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateDepartmentRequest(BaseModel):
    name: str
    description: Optional[str] = None
