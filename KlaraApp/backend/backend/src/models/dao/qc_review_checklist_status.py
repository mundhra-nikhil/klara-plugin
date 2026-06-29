import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.dao.base import Base


class QCReviewChecklistStatus(Base):
    __tablename__ = "qc_review_checklist_statuses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_id = Column(UUID(as_uuid=True), ForeignKey("qc_reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    checklist_item_id = Column(UUID(as_uuid=True), ForeignKey("checklist_items.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False)  # "pass", "fail", "warn", "pending"
    details = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    review = relationship("QCReview", foreign_keys=[review_id])
    checklist_item = relationship("ChecklistItem", foreign_keys=[checklist_item_id])
