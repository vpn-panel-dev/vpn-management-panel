"""add async operations and node cached fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-08
"""

import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'nodes',
        sa.Column('health_status', sa.String(), nullable=False, server_default='unknown'),
    )
    op.add_column('nodes', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'nodes',
        sa.Column('provision_status', sa.String(), nullable=False, server_default='pending'),
    )
    op.create_table(
        'async_operations',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=True),
        sa.Column('target_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.String(), nullable=True),
        sa.Column('result', sa.String(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('idempotency_key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('async_operations')
    op.drop_column('nodes', 'provision_status')
    op.drop_column('nodes', 'last_seen_at')
    op.drop_column('nodes', 'health_status')
