"""add s3, s4 to nodes

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-30
"""

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('nodes', sa.Column('s3', sa.Integer(), nullable=True))
    op.add_column('nodes', sa.Column('s4', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('nodes', 's4')
    op.drop_column('nodes', 's3')
