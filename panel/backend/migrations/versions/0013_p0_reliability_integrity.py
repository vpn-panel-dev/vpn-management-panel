"""p0 reliability integrity

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'nodes',
        sa.Column('reachability_status', sa.String(), nullable=False, server_default='unknown'),
    )
    op.add_column(
        'nodes', sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('nodes', sa.Column('last_heartbeat_error', sa.String(), nullable=True))
    op.add_column(
        'nodes', sa.Column('sync_status', sa.String(), nullable=False, server_default='pending')
    )
    op.add_column('nodes', sa.Column('sync_error', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        DELETE FROM peers
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM peers
            GROUP BY node_id, user_id
        )
        """
    )
    op.create_unique_constraint('uq_peers_node_user', 'peers', ['node_id', 'user_id'])


def downgrade() -> None:
    op.drop_constraint('uq_peers_node_user', 'peers', type_='unique')
    op.drop_column('nodes', 'last_synced_at')
    op.drop_column('nodes', 'sync_error')
    op.drop_column('nodes', 'sync_status')
    op.drop_column('nodes', 'last_heartbeat_error')
    op.drop_column('nodes', 'last_heartbeat_at')
    op.drop_column('nodes', 'reachability_status')
