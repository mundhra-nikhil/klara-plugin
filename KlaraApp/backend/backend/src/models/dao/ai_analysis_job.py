import uuid
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, SmallInteger,
    Integer, Enum, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.models.dao.base import Base
from src.models.enum.job_type import AIJobType
from src.models.enum.job_status import AIJobStatus


class AIAnalysisJob(Base):
    __tablename__ = "ai_analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    job_type = Column(Enum(AIJobType, name="ai_job_type"), nullable=False)
    status = Column(Enum(AIJobStatus, name="ai_job_status"), nullable=False, default=AIJobStatus.PENDING)
    queue_job_id = Column(String(255), nullable=True)
    model_used = Column(String(100), nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    results = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(SmallInteger, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="ai_analysis_jobs")
    qc_findings = relationship("QCFinding", back_populates="analysis_job")
