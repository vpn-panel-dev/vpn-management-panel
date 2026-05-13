"""traffic stats: peer_traffic_samples table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-30
"""

import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('peers', sa.Column('raw_rx', sa.BigInteger(), nullable=True))
    op.add_column('peers', sa.Column('raw_tx', sa.BigInteger(), nullable=True))
    op.add_column('peers', sa.Column('last_handshake', sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        'peer_traffic_samples',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('peer_id', sa.String(), nullable=False),
        sa.Column('sampled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('rx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tx_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['peer_id'], ['peers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pts_peer_sampled', 'peer_traffic_samples', ['peer_id', 'sampled_at'])


def downgrade() -> None:
    op.drop_index('ix_pts_peer_sampled', table_name='peer_traffic_samples')
    op.drop_table('peer_traffic_samples')
    op.drop_column('peers', 'last_handshake')
    op.drop_column('peers', 'raw_tx')
    op.drop_column('peers', 'raw_rx')
