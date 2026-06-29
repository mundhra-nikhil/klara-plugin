import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.dao.base import Base


class QCReview(Base):
    __tablename__ = "qc_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    checklist_id = Column(UUID(as_uuid=True), ForeignKey("qc_checklists.id"), nullable=True)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="in_progress")
    notes = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document = relationship("Document", back_populates="qc_reviews")
    checklist = relationship("QCChecklist")
    operator = relationship("User", foreign_keys=[operator_id])
