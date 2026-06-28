"""add telegram proxy settings and node state tables

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-26
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telegram_proxy_settings',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('port', sa.Integer(), nullable=False, server_default='443'),
        sa.Column('secret_encrypted', sa.String(), nullable=True),
        sa.Column('primary_node_id', sa.String(), nullable=True),
        sa.Column('last_rotation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_rotation_reason', sa.String(), nullable=True),
        sa.Column('last_rotation_error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['primary_node_id'], ['nodes.id'], ondelete='SET NULL'),
    )
    op.create_table(
        'telegram_proxy_node_states',
        sa.Column('node_id', sa.String(), nullable=False, primary_key=True),
        sa.Column('status', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('public_host', sa.String(), nullable=True),
        sa.Column('public_port', sa.Integer(), nullable=True),
        sa.Column('last_applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
    )

    settings = sa.table(
        'telegram_proxy_settings',
        sa.column('id', sa.String()),
        sa.column('enabled', sa.Boolean()),
        sa.column('port', sa.Integer()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        settings,
        [
            {
                'id': 'default',
                'enabled': False,
                'port': 443,
                'created_at': now,
                'updated_at': now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table('telegram_proxy_node_states')
    op.drop_table('telegram_proxy_settings')
