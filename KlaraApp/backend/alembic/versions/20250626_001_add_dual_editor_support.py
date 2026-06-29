"""add dual editor support

Revision ID: 20250626_001
Revises: initial_tables_creation
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa

revision = '20250626_001'
down_revision = '14f6540448af'
branch_labels = None
depends_on = None


def upgrade():
    """Add dual editor architecture support to documents table."""

    # Add storage_type column (default 'local' for existing documents)
    op.add_column(
        'documents',
        sa.Column('storage_type', sa.String(20), nullable=False, server_default='local')
    )

    # Add editor_type column (default 'onlyoffice' for existing documents)
    op.add_column(
        'documents',
        sa.Column('editor_type', sa.String(20), nullable=False, server_default='onlyoffice')
    )

    # Add SharePoint metadata columns
    op.add_column(
        'documents',
        sa.Column('sharepoint_site_id', sa.String(255), nullable=True)
    )

    op.add_column(
        'documents',
        sa.Column('sharepoint_drive_id', sa.String(255), nullable=True)
    )

    op.add_column(
        'documents',
        sa.Column('sharepoint_item_id', sa.String(255), nullable=True)
    )

    op.add_column(
        'documents',
        sa.Column('sharepoint_folder_id', sa.String(255), nullable=True, server_default='root')
    )

    # Create indexes for SharePoint lookups
    op.create_index(
        'ix_documents_storage_type',
        'documents',
        ['storage_type']
    )

    op.create_index(
        'ix_documents_sharepoint_ids',
        'documents',
        ['sharepoint_site_id', 'sharepoint_item_id']
    )


def downgrade():
    """Remove dual editor architecture support."""

    # Drop indexes
    op.drop_index('ix_documents_sharepoint_ids', table_name='documents')
    op.drop_index('ix_documents_storage_type', table_name='documents')

    # Drop columns
    op.drop_column('documents', 'sharepoint_folder_id')
    op.drop_column('documents', 'sharepoint_item_id')
    op.drop_column('documents', 'sharepoint_drive_id')
    op.drop_column('documents', 'sharepoint_site_id')
    op.drop_column('documents', 'editor_type')
    op.drop_column('documents', 'storage_type')