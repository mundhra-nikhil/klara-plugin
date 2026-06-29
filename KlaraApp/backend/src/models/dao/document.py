import uuid
from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, SmallInteger,
    Integer, BigInteger, Enum, func, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.models.dao.base import Base
from src.models.enum.document_type import DocumentType
from src.models.enum.document_status import DocumentStatus


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    document_type = Column(Enum(DocumentType, name="document_type"), nullable=False)
    status = Column(Enum(DocumentStatus, name="document_status"), nullable=False, default=DocumentStatus.RECEIVED, index=True)
    blob_url = Column(Text, nullable=False)
    blob_container = Column(String(255), nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    assigned_specialist_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)

    # Dual editor architecture support
    storage_type = Column(String(20), nullable=False, server_default="local")  # 'local' or 'sharepoint'
    editor_type = Column(String(20), nullable=False, server_default="onlyoffice")  # 'onlyoffice' or 'word_online'
    # SharePoint metadata for cloud storage
    sharepoint_site_id = Column(String(255), nullable=True)
    sharepoint_drive_id = Column(String(255), nullable=True)
    sharepoint_item_id = Column(String(255), nullable=True)
    sharepoint_folder_id = Column(String(255), nullable=True, server_default="root")
    priority = Column(SmallInteger, default=3)
    deadline = Column(DateTime(timezone=True), nullable=True, index=True)
    version = Column(Integer, default=1)
    # How Klara runs its QA on this document:
    #   "auto"          → first-pass QA runs automatically on upload (default)
    #   "review_assist" → no auto-run; the reviewer works first, then triggers
    #                     Klara on demand to surface what they missed.
    validation_mode = Column(String(20), nullable=False, server_default="auto")
    # Lifecycle timestamps powering the reporting metrics (turnaround / LOE).
    # submitted_at == upload/intake time; completed_at == when the document is
    # marked COMPLETED. Backfilled to created_at for pre-existing rows.
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_documents_client_status", "client_id", "status"),
        Index("ix_documents_active", "id", postgresql_where=(deleted_at == None)),
    )

    client = relationship("Client", back_populates="documents")
    assigned_specialist = relationship("User", back_populates="assigned_documents", foreign_keys=[assigned_specialist_id])
    ai_analysis_jobs = relationship("AIAnalysisJob", back_populates="document")
    qc_findings = relationship("QCFinding", back_populates="document")
    versions = relationship("DocumentVersion", back_populates="document")
    qc_reviews = relationship("QCReview", back_populates="document")

    @property
    def ai_status(self) -> str:
        if not self.ai_analysis_jobs:
            return "not_started"
        latest = None
        for job in self.ai_analysis_jobs:
            if not latest or job.created_at > latest.created_at:
                latest = job
        if not latest:
            return "not_started"
        status_val = latest.status
        if hasattr(status_val, "value"):
            status_val = status_val.value
        if status_val in ("pending", "running", "retrying"):
            return "running"
        elif status_val == "completed":
            return "completed"
        elif status_val == "failed":
            return "failed"
        return "not_started"



class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    blob_url = Column(Text, nullable=False)
    diff_metadata = Column(JSONB, nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="versions")
    created_by = relationship("User", foreign_keys=[created_by_id])


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    notification_type = Column(String(50), nullable=False)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    reference_type = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])


class JobQueueEvent(Base):
    __tablename__ = "job_queue_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("ai_analysis_jobs.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)
    ttl_seconds = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
