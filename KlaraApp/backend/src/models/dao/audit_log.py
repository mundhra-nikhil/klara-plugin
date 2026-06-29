from sqlalchemy import (
    Column, String, DateTime, BigInteger, Text, Enum, Index, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

from src.models.dao.base import Base
from src.models.enum.job_status import AuditAction, ActorType


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(Enum(AuditAction, name="audit_action"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    actor_type = Column(Enum(ActorType, name="actor_type"), nullable=False)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
    correlation_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_actor", "actor_id"),
        Index("ix_audit_created", "created_at"),
    )
