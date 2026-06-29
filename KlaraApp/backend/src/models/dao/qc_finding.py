import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.models.dao.base import Base
from src.models.enum.finding_severity import FindingSeverity
from src.models.enum.finding_status import FindingStatus


class QCFinding(Base):
    __tablename__ = "qc_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    analysis_job_id = Column(UUID(as_uuid=True), ForeignKey("ai_analysis_jobs.id"), nullable=True)
    finding_type = Column(Enum("formatting", "spelling", "consistency", "compliance", "style", "metadata", name="finding_type"), nullable=False)
    severity = Column(Enum(FindingSeverity, name="severity"), nullable=False)
    location = Column(JSONB, nullable=True)
    description = Column(Text, nullable=False)
    suggested_fix = Column(Text, nullable=True)
    status = Column(Enum(FindingStatus, name="finding_status"), default=FindingStatus.OPEN)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="qc_findings")
    analysis_job = relationship("AIAnalysisJob", back_populates="qc_findings")
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])
