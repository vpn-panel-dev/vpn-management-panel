"""keypair on user, metadata on node, status on peer

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-29
"""

import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Node: add cached server metadata fields
    op.add_column('nodes', sa.Column('server_public_key', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('server_endpoint', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('listen_port', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('jc', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('jmin', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('jmax', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('s1', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('s2', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('h1', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('h2', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('h3', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('h4', sa.Integer(), nullable=True))

    # User: add shared keypair + vpn_ip
    op.add_column('users', sa.Column('public_key', sa.String(), nullable=True))
    op.add_column('users', sa.Column('private_key', sa.String(), nullable=True))
    op.add_column('users', sa.Column('vpn_ip', sa.String(), nullable=True))

    # Peer: add status, drop old key/ip columns
    op.add_column(
        'peers',
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
    )
    op.drop_column('peers', 'public_key')
    op.drop_column('peers', 'private_key')
    op.drop_column('peers', 'allowed_ip')


def downgrade() -> None:
    op.add_column('peers', sa.Column('allowed_ip', sa.String(), nullable=True))
    op.add_column('peers', sa.Column('private_key', sa.String(), nullable=True))
    op.add_column('peers', sa.Column('public_key', sa.String(), nullable=True))
    op.drop_column('peers', 'status')

    op.drop_column('users', 'vpn_ip')
    op.drop_column('users', 'private_key')
    op.drop_column('users', 'public_key')

    for col in (
        'h4',
        'h3',
        'h2',
        'h1',
        's2',
        's1',
        'jmax',
        'jmin',
        'jc',
        'listen_port',
        'server_endpoint',
        'server_public_key',
    ):
        op.drop_column('nodes', col)
