"""add last_error to nodes

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-05
"""

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('nodes', sa.Column('last_error', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('nodes', 'last_error')
