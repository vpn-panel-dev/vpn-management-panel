"""local user lifecycle

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users', sa.Column('lifecycle_status', sa.String(), nullable=False, server_default='active')
    )
    op.add_column('users', sa.Column('expire_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'users',
        sa.Column('traffic_limit_bytes', sa.BigInteger(), nullable=False, server_default='0'),
    )
    op.add_column(
        'users',
        sa.Column('traffic_reset_policy', sa.String(), nullable=False, server_default='manual'),
    )
    op.add_column('users', sa.Column('traffic_reset_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('public_token', sa.String(), nullable=True))
    op.execute('UPDATE users SET public_token = id WHERE public_token IS NULL')
    op.alter_column('users', 'public_token', nullable=False)
    op.create_index(op.f('ix_users_public_token'), 'users', ['public_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_public_token'), table_name='users')
    op.drop_column('users', 'public_token')
    op.drop_column('users', 'traffic_reset_at')
    op.drop_column('users', 'traffic_reset_policy')
    op.drop_column('users', 'traffic_limit_bytes')
    op.drop_column('users', 'expire_at')
    op.drop_column('users', 'lifecycle_status')
