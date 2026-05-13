"""add private_key to nodes

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-30
"""

import sqlalchemy as sa
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('nodes', sa.Column('private_key', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('nodes', 'private_key')
