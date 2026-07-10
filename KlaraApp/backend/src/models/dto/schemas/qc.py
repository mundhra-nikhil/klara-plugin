from pydantic import BaseModel
from typing import Optional, List, Union
from uuid import UUID
from datetime import datetime

from src.models.enum.finding_severity import FindingSeverity
from src.models.enum.finding_status import FindingStatus
from src.models.enum.job_status import FindingType


class FindingResponse(BaseModel):
    id: UUID
    document_id: UUID
    analysis_job_id: Optional[UUID]
    finding_type: FindingType
    severity: FindingSeverity
    location: Optional[Union[dict, str]]
    description: str
    suggested_fix: Optional[str]
    status: FindingStatus
    resolved_by_user_id: Optional[UUID]
    resolved_at: Optional[datetime]
    created_at: datetime
    # Additional fields for frontend compatibility
    review_id: Optional[UUID] = None
    paragraph_index: Optional[int] = None
    anchor_text: Optional[str] = None
    title: Optional[str] = None
    rule_name: Optional[str] = None
    original_text: Optional[str] = None
    replacement_text: Optional[str] = None
    formatting_fix: Optional[dict] = None

    model_config = {"from_attributes": True}


class ResolveFindingRequest(BaseModel):
    status: FindingStatus
    # Optional inline edit: when set, this becomes the actual text applied to the
    # document (instead of the AI's suggested replacement_text). Stored alongside
    # the finding so the side-by-side viewer can render the edited result.
    applied_text: Optional[str] = None
    note: Optional[str] = None
    # Additional fields for frontend compatibility
    resolution_notes: Optional[str] = None
    auto_resolved: Optional[bool] = None
    not_found_in_document: Optional[bool] = None


class CreateReviewRequest(BaseModel):
    document_id: UUID
    checklist_id: Optional[UUID] = None
    notes: Optional[str] = None


class SaveChecklistItemStatusRequest(BaseModel):
    checklist_item_id: UUID
    status: str
    details: Optional[str] = None


class QCReviewChecklistStatusResponse(BaseModel):
    id: UUID
    review_id: UUID
    checklist_item_id: UUID
    status: str
    details: Optional[str]
    updated_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CompleteReviewRequest(BaseModel):
    notes: Optional[str] = None


class ReviewResponse(BaseModel):
    id: UUID
    document_id: UUID
    checklist_id: Optional[UUID]
    operator_id: UUID
    status: str
    notes: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ChecklistItemResponse(BaseModel):
    id: UUID
    group: str
    title: str
    description: Optional[str] = None
    is_automated: bool = True
    ai_finding_type_mapping: Optional[str] = None
    result: str = "pending"
    details: Optional[str] = None
    order: int

    model_config = {"from_attributes": True}


class ChecklistResponse(BaseModel):
    id: UUID
    document_type: str
    name: str
    version: int
    schema_definition: dict
    is_active: bool
    created_at: datetime
    items: List[ChecklistItemResponse] = []

    model_config = {"from_attributes": True}
