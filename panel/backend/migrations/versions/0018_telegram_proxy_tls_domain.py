"""add telegram proxy tls domain

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-29
"""

import sqlalchemy as sa
from alembic import op

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'telegram_proxy_settings',
        sa.Column('tls_domain', sa.String(), nullable=False, server_default='cloudsyncpro.net'),
    )
    op.alter_column('telegram_proxy_settings', 'tls_domain', server_default=None)


def downgrade() -> None:
    op.drop_column('telegram_proxy_settings', 'tls_domain')
