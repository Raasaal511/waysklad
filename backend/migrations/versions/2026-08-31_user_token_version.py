"""users.token_version — отзыв JWT-токенов (смена пароля / logout со всех устройств)

Revision ID: e7c5a3f9d1b4
Revises: d3a9f6c1b8e2
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7c5a3f9d1b4'
down_revision: Union[str, Sequence[str], None] = 'd3a9f6c1b8e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('users', 'token_version')
