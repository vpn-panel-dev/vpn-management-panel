"""use bigint for remnawave telegram ids

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'remnawave_users',
        'telegram_id',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'remnawave_users',
        'telegram_id',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
