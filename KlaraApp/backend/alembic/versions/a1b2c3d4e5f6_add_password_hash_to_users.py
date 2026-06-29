"""add_password_hash_to_users

Revision ID: a1b2c3d4e5f6
Revises: 14f6540448af
Create Date: 2026-05-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '14f6540448af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add password_hash column
    op.add_column('users', sa.Column('password_hash', sa.String(length=255), nullable=True))
    
    # Make azure_ad_oid nullable to support password-based authentication
    op.alter_column('users', 'azure_ad_oid', nullable=True)


def downgrade() -> None:
    # Revert azure_ad_oid to non-nullable
    op.alter_column('users', 'azure_ad_oid', nullable=False)
    
    # Remove password_hash column
    op.drop_column('users', 'password_hash')
