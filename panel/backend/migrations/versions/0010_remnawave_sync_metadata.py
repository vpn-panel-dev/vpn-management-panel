import sqlalchemy as sa
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'remnawave_users',
        sa.Column('sync_status', sa.String(), nullable=False, server_default='synced'),
    )
    op.add_column('remnawave_users', sa.Column('sync_reason', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('remnawave_users', 'sync_reason')
    op.drop_column('remnawave_users', 'sync_status')
