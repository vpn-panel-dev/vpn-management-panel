"""add local amneziawg traffic accounting tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-31
"""

import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'local_amneziawg_traffic_deltas',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('peer_id', sa.String(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_sync_id', sa.String(), nullable=True),
        sa.Column('previous_rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('previous_tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('current_rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('current_tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('rx_delta_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_delta_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_delta_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('rx_reset_detected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('tx_reset_detected', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['peer_id'], ['peers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index(
        'ix_local_awg_deltas_peer_observed',
        'local_amneziawg_traffic_deltas',
        ['peer_id', 'observed_at'],
    )
    op.create_index(
        'ix_local_awg_deltas_user_observed',
        'local_amneziawg_traffic_deltas',
        ['user_id', 'observed_at'],
    )
    op.create_index(
        'ix_local_awg_deltas_node_observed',
        'local_amneziawg_traffic_deltas',
        ['node_id', 'observed_at'],
    )

    op.create_table(
        'local_amneziawg_user_daily_traffic',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'day'),
    )
    op.create_index(
        'ix_local_awg_user_daily_user_day',
        'local_amneziawg_user_daily_traffic',
        ['user_id', 'day'],
    )

    op.create_table(
        'local_amneziawg_user_node_daily_traffic',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'node_id', 'day'),
    )
    op.create_index(
        'ix_local_awg_user_node_daily_user_node_day',
        'local_amneziawg_user_node_daily_traffic',
        ['user_id', 'node_id', 'day'],
    )

    op.create_table(
        'local_amneziawg_user_lifetime_traffic',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False, unique=True),
        sa.Column('rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'local_amneziawg_user_node_lifetime_traffic',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('node_id', sa.String(), nullable=False),
        sa.Column('rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['node_id'], ['nodes.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'node_id'),
    )
    op.create_index(
        'ix_local_awg_user_node_lifetime_user_node',
        'local_amneziawg_user_node_lifetime_traffic',
        ['user_id', 'node_id'],
    )

    op.create_table(
        'local_amneziawg_traffic_settings',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('raw_sample_retention_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('local_amneziawg_traffic_settings')
    op.drop_index(
        'ix_local_awg_user_node_lifetime_user_node',
        table_name='local_amneziawg_user_node_lifetime_traffic',
    )
    op.drop_table('local_amneziawg_user_node_lifetime_traffic')
    op.drop_table('local_amneziawg_user_lifetime_traffic')
    op.drop_index(
        'ix_local_awg_user_node_daily_user_node_day',
        table_name='local_amneziawg_user_node_daily_traffic',
    )
    op.drop_table('local_amneziawg_user_node_daily_traffic')
    op.drop_index(
        'ix_local_awg_user_daily_user_day',
        table_name='local_amneziawg_user_daily_traffic',
    )
    op.drop_table('local_amneziawg_user_daily_traffic')
    op.drop_index('ix_local_awg_deltas_node_observed', table_name='local_amneziawg_traffic_deltas')
    op.drop_index('ix_local_awg_deltas_user_observed', table_name='local_amneziawg_traffic_deltas')
    op.drop_index('ix_local_awg_deltas_peer_observed', table_name='local_amneziawg_traffic_deltas')
    op.drop_table('local_amneziawg_traffic_deltas')
