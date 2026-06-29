"""merge branches

Revision ID: 25b5240270cd
Revises: 20250626_002, b7d2e9a1c4f0
Create Date: 2026-06-26 08:14:53.813131

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '25b5240270cd'
down_revision: Union[str, None] = ('20250626_002', 'b7d2e9a1c4f0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
