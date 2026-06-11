"""use bigint for remnawave traffic counters

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-11
"""

import sqlalchemy as sa
from alembic import op

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'remnawave_users',
        'traffic_limit_bytes',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        existing_server_default='0',
    )
    op.alter_column(
        'remnawave_users',
        'traffic_used_bytes',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        existing_server_default='0',
    )
    op.alter_column(
        'remnawave_users',
        'lifetime_used_traffic_bytes',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        existing_server_default='0',
    )


def downgrade() -> None:
    op.alter_column(
        'remnawave_users',
        'lifetime_used_traffic_bytes',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default='0',
    )
    op.alter_column(
        'remnawave_users',
        'traffic_used_bytes',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default='0',
    )
    op.alter_column(
        'remnawave_users',
        'traffic_limit_bytes',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default='0',
    )
