import uuid
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Text, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.dao.base import Base


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checklist_id = Column(UUID(as_uuid=True), ForeignKey("qc_checklists.id"), nullable=False)
    label = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    ai_finding_type_mapping = Column(Enum("formatting", "spelling", "consistency", "compliance", "style", "metadata", name="finding_type_item", create_type=False), nullable=True)
    sort_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    checklist = relationship("QCChecklist", back_populates="items")

    @property
    def title(self) -> str:
        return self.label

    @property
    def group(self) -> str:
        if self.ai_finding_type_mapping:
            val = self.ai_finding_type_mapping.value if hasattr(self.ai_finding_type_mapping, 'value') else str(self.ai_finding_type_mapping)
            if val == "compliance":
                return "Citations"
            elif val == "consistency":
                return "Numbering"
            elif val == "style":
                return "Formatting"
            elif val == "formatting":
                return "Document setup"
            return val.capitalize()
        return "Manual review"

    @property
    def is_automated(self) -> bool:
        return self.ai_finding_type_mapping is not None

    @property
    def order(self) -> int:
        return self.sort_order

    @property
    def result(self) -> str:
        return "pending"

    @property
    def details(self) -> str:
        return self.description or ""
