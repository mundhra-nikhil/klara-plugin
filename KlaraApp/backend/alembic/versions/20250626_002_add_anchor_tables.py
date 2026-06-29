"""Database migration for anchor management system.

Revision ID: 20250626_002
Revises: 20250626_001_add_dual_editor_support
Create Date: 2026-06-26

This migration creates tables for the durable anchoring system
that maintains finding references across document edits and different editors.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '20250626_002'
down_revision = '20250626_001'
branch_labels = None
depends_on = None


def upgrade():
    """Create anchor management tables."""

    # Create finding_anchors table
    op.create_table(
        'finding_anchors',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('finding_id', UUID(as_uuid=True), sa.ForeignKey('qc_findings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('anchor_type', sa.String(50), nullable=False),
        sa.Column('primary_anchor_data', sa.JSON(), nullable=False),
        sa.Column('fallback_anchors', sa.JSON(), nullable=True, server_default='[]'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('editor_type', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolution_history', sa.JSON(), nullable=True, server_default='[]')
    )

    # Create indexes for finding_anchors
    op.create_index('ix_finding_anchors_finding_id', 'finding_anchors', ['finding_id'])
    op.create_index('ix_finding_anchors_type', 'finding_anchors', ['anchor_type', 'editor_type'])

    # Create anchor_resolutions table
    op.create_table(
        'anchor_resolutions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('anchor_id', UUID(as_uuid=True), sa.ForeignKey('finding_anchors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolution_method', sa.String(50), nullable=False),
        sa.Column('resolution_time_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('editor_context', sa.JSON(), nullable=True),
        sa.Column('document_version', sa.String(100), nullable=True)
    )

    # Create indexes for anchor_resolutions
    op.create_index('ix_anchor_resolutions_anchor_id', 'anchor_resolutions', ['anchor_id'])
    op.create_index('ix_anchor_resolutions_success', 'anchor_resolutions', ['success', 'resolved_at'])

    # Create document_anchor_cache table
    op.create_table(
        'document_anchor_cache',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('cache_key', sa.String(255), nullable=False),
        sa.Column('resolved_position', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('access_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true')
    )

    # Create indexes for document_anchor_cache
    op.create_index('ix_document_anchor_cache_document', 'document_anchor_cache', ['document_id'])
    op.create_index('ix_document_anchor_cache_key', 'document_anchor_cache', ['cache_key'])
    op.create_index('ix_document_anchor_cache_valid', 'document_anchor_cache', ['is_valid', 'expires_at'])


def downgrade():
    """Remove anchor management tables."""

    # Drop tables
    op.drop_table('document_anchor_cache')
    op.drop_table('anchor_resolutions')
    op.drop_table('finding_anchors')
