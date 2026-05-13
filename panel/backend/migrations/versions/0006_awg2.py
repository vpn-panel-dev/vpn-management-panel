"""awg2 format: h1-h4 to varchar, add i1-i5/mtu on nodes, add psk_key on peers

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-01
"""

import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert h1-h4 from Integer to VARCHAR (AWG2 uses "x-y" composite strings)
    for col in ('h1', 'h2', 'h3', 'h4'):
        op.alter_column(
            'nodes',
            col,
            type_=sa.String(),
            existing_type=sa.Integer(),
            postgresql_using=f'{col}::text',
        )

    # Traffic imitation parameters (AWG2)
    op.add_column('nodes', sa.Column('i1', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('i2', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('i3', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('i4', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('i5', sa.String(), nullable=True))
    op.add_column('nodes', sa.Column('mtu', sa.String(), nullable=True))

    # PresharedKey per peer
    op.add_column('peers', sa.Column('psk_key', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('peers', 'psk_key')

    op.drop_column('nodes', 'mtu')
    for col in ('i5', 'i4', 'i3', 'i2', 'i1'):
        op.drop_column('nodes', col)

    for col in ('h1', 'h2', 'h3', 'h4'):
        op.alter_column(
            'nodes',
            col,
            type_=sa.Integer(),
            existing_type=sa.String(),
            postgresql_using=f"NULLIF(split_part({col}, '-', 1), '')::integer",
        )
