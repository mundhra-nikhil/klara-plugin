"""Database models for anchor management.

This module defines SQLAlchemy models for storing and managing
finding anchors across different document editors and edit sessions.
"""

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Float,
    Integer, JSONB, UUID
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.models.dao.base import Base
from datetime import datetime, timezone


class FindingAnchor(Base):
    """
    Finding anchor model for durable finding references.

    Stores anchor data for maintaining finding positions across document edits
    and different editor types.
    """
    __tablename__ = "finding_anchors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: uuid.uuid4())
    finding_id = Column(UUID(as_uuid=True), ForeignKey("qc_findings.id", ondelete="CASCADE"), nullable=False, index=True)

    # Anchor type and primary data
    anchor_type = Column(String(50), nullable=False)  # 'content_control', 'bookmark', etc.
    primary_anchor_data = Column(JSONB, nullable=False)  # Primary anchor information

    # Fallback anchors
    fallback_anchors = Column(JSONB, nullable=True, default=list)  # Secondary/tertiary anchors

    # Metadata and tracking
    confidence_score = Column(Float, default=1.0)  # 0.0-1.0 confidence in anchor stability
    editor_type = Column(String(20), nullable=False)  # 'onlyoffice' or 'word_online'

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Resolution history
    resolution_history = Column(JSONB, default=list)  # Track resolution attempts

    # Relationships
    finding = relationship("QCFinding", back_populates="anchors")

    __table_args__ = (
        {"comment": "Finding anchors for durable references across document edits"},
    )


class AnchorResolution(Base):
    """
    Track anchor resolution attempts and success rates.

    This table provides analytics on anchor stability and helps
    identify which anchor types work best for different scenarios.
    """
    __tablename__ = "anchor_resolutions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: uuid.uuid4())
    anchor_id = Column(UUID(as_uuid=True), ForeignKey("finding_anchors.id", ondelete="CASCADE"), nullable=False, index=True)

    # Resolution attempt details
    resolved_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolution_method = Column(String(50), nullable=False)  # Which anchor type was used
    resolution_time_ms = Column(Integer, nullable=True)  # Time taken to resolve
    success = Column(Boolean, nullable=False, default=False)

    # Error tracking
    error_message = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)

    # Context information
    editor_context = Column(JSONB, nullable=True)  # Editor state during resolution
    document_version = Column(String(100), nullable=True)  # Document version if available

    __table_args__ = (
        {"comment": "Track anchor resolution success rates and methods"},
    )


class DocumentAnchorCache(Base):
    """
    Cache for frequently used anchor lookups.

    Improves performance by caching resolved anchor positions
    and avoiding repeated expensive resolution operations.
    """
    __tablename__ = "document_anchor_cache"

    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: uuid.uuid4())
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    # Cache key for the anchor (hash of finding characteristics)
    cache_key = Column(String(255), nullable=False, index=True)

    # Cached resolution data
    resolved_position = Column(JSONB, nullable=False)

    # Cache metadata
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_accessed = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    access_count = Column(Integer, default=0, nullable=False)

    # Cache validity
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        {"comment": "Cache for frequently accessed anchor positions"},
    )


# Update the QCFinding model to include anchors relationship
# This should be added to the existing models/dao/qc_finding.py file

# Add this to QCFinding class:
# anchors = relationship("FindingAnchor", back_populates="finding", cascade="all, delete-orphan")

# Add this to Document model:
# anchor_cache = relationship("DocumentAnchorCache", cascade="all, delete-orphan")
