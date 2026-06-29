"""add document lifecycle timestamps and validation_mode

Adds:
  * documents.validation_mode  — "auto" | "review_assist" (On-Demand Klara)
  * documents.submitted_at      — intake/upload time (reporting)
  * documents.completed_at      — when marked COMPLETED (reporting)

Existing rows are backfilled: submitted_at <- created_at, and completed_at
<- created_at for rows already in the COMPLETED status so the new List Report
has sensible historical values.

Revision ID: b7d2e9a1c4f0
Revises: 0bc41e47fb42
Create Date: 2026-06-04 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7d2e9a1c4f0'
down_revision: Union[str, None] = '0bc41e47fb42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'documents',
        sa.Column('validation_mode', sa.String(length=20), nullable=False, server_default='auto'),
    )
    op.add_column(
        'documents',
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    op.add_column(
        'documents',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill from existing data so historical rows have meaningful metrics.
    # add_column with server_default now() stamped every existing row with the
    # migration time; reset those to the real intake time (created_at).
    op.execute("UPDATE documents SET submitted_at = created_at")
    op.execute("UPDATE documents SET completed_at = created_at WHERE status = 'COMPLETED' AND completed_at IS NULL")

    op.create_index(op.f('ix_documents_submitted_at'), 'documents', ['submitted_at'], unique=False)
    op.create_index(op.f('ix_documents_completed_at'), 'documents', ['completed_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documents_completed_at'), table_name='documents')
    op.drop_index(op.f('ix_documents_submitted_at'), table_name='documents')
    op.drop_column('documents', 'completed_at')
    op.drop_column('documents', 'submitted_at')
    op.drop_column('documents', 'validation_mode')
