"""widen products/product_variants.barcode to support alphanumeric codes

Revision ID: c8a2d6e5f1b9
Revises: b3f7e1a9c4d2
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8a2d6e5f1b9'
down_revision: Union[str, Sequence[str], None] = 'b3f7e1a9c4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'products', 'barcode',
        existing_type=sa.String(length=14), type_=sa.String(length=32),
    )
    op.alter_column(
        'product_variants', 'barcode',
        existing_type=sa.String(length=14), type_=sa.String(length=32),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'product_variants', 'barcode',
        existing_type=sa.String(length=32), type_=sa.String(length=14),
    )
    op.alter_column(
        'products', 'barcode',
        existing_type=sa.String(length=32), type_=sa.String(length=14),
    )
