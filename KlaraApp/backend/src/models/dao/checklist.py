import uuid
from sqlalchemy import Column, String, DateTime, Integer, Boolean, Enum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.models.dao.base import Base
from src.models.enum.document_type import DocumentType


class QCChecklist(Base):
    __tablename__ = "qc_checklists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_type = Column(Enum(DocumentType, name="document_type_checklist", create_type=False), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1)
    schema_definition = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("ChecklistItem", back_populates="checklist")
