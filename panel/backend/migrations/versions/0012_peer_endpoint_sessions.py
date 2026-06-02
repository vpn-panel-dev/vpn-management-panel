"""add peer endpoint sessions and online threshold

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-02
"""

import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('peers', sa.Column('endpoint', sa.String(), nullable=True))

    op.create_table(
        'peer_endpoint_sessions',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('peer_id', sa.String(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_handshake', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['peer_id'], ['peers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(
        'ix_peer_endpoint_sessions_peer_seen',
        'peer_endpoint_sessions',
        ['peer_id', 'last_seen_at'],
    )
    op.create_index(
        'ix_peer_endpoint_sessions_user_seen',
        'peer_endpoint_sessions',
        ['user_id', 'last_seen_at'],
    )
    op.create_index(
        'ix_peer_endpoint_sessions_node_seen',
        'peer_endpoint_sessions',
        ['node_id', 'last_seen_at'],
    )
    op.add_column(
        'local_amneziawg_traffic_settings',
        sa.Column(
            'peer_online_threshold_seconds', sa.Integer(), nullable=False, server_default='180'
        ),
    )


def downgrade() -> None:
    op.drop_column('local_amneziawg_traffic_settings', 'peer_online_threshold_seconds')
    op.drop_index('ix_peer_endpoint_sessions_node_seen', table_name='peer_endpoint_sessions')
    op.drop_index('ix_peer_endpoint_sessions_user_seen', table_name='peer_endpoint_sessions')
    op.drop_index('ix_peer_endpoint_sessions_peer_seen', table_name='peer_endpoint_sessions')
    op.drop_table('peer_endpoint_sessions')
    op.drop_column('peers', 'endpoint')
