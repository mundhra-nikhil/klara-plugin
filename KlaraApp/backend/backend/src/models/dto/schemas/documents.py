from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime

from src.models.enum.document_type import DocumentType
from src.models.enum.document_status import DocumentStatus


class CreateDocumentRequest(BaseModel):
    client_id: UUID
    title: str = Field(max_length=500)
    document_type: DocumentType
    priority: int = Field(default=3, ge=1, le=4)
    deadline: Optional[datetime] = None
    metadata: Optional[dict] = None
    # "auto" → run first-pass QA on upload; "review_assist" → run on demand.
    validation_mode: str = Field(default="auto", pattern="^(auto|review_assist)$")

    # Dual editor architecture support
    storage_type: str = Field(default="local", pattern="^(local|sharepoint)$")
    editor_type: str = Field(default="onlyoffice", pattern="^(onlyoffice|word_online)$")
    # SharePoint metadata for cloud storage
    sharepoint_site_id: Optional[str] = None
    sharepoint_drive_id: Optional[str] = None
    sharepoint_item_id: Optional[str] = None
    sharepoint_folder_id: Optional[str] = "root"


class CreateDocumentResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    upload_url: str
    ws_channel: str


class UpdateDocumentStatusRequest(BaseModel):
    status: DocumentStatus
    notes: Optional[str] = None


class AssignDocumentRequest(BaseModel):
    specialist_id: Optional[UUID] = None
    qc_operator_id: Optional[UUID] = None
    proofreader_id: Optional[UUID] = None


class DocumentResponse(BaseModel):
    id: UUID
    client_id: UUID
    # Resolved client name (populated by service layer)
    client_name: Optional[str] = None
    title: str
    document_type: DocumentType
    status: DocumentStatus
    blob_url: str
    priority: int
    deadline: Optional[datetime] = None
    assigned_specialist_id: Optional[UUID] = None
    # Resolved specialist display name (populated by service layer)
    assigned_specialist_name: Optional[str] = None
    metadata_: Optional[dict] = Field(default=None, alias="metadata_")
    version: int
    validation_mode: str = "auto"
    ai_status: Optional[str] = "not_started"
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    # Dual editor architecture support
    storage_type: str = "local"  # 'local' or 'sharepoint'
    editor_type: str = "onlyoffice"  # 'onlyoffice' or 'word_online'
    # SharePoint metadata for cloud storage
    sharepoint_site_id: Optional[str] = None
    sharepoint_drive_id: Optional[str] = None
    sharepoint_item_id: Optional[str] = None
    sharepoint_folder_id: Optional[str] = "root"

    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentListResponse(BaseModel):
    data: List[DocumentResponse]
    next_cursor: Optional[str] = None
    total: int


class DocumentVersionResponse(BaseModel):
    id: UUID
    version_number: int
    blob_url: str
    diff_metadata: Optional[dict] = None
    created_by_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}
