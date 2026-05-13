"""add remnawave settings, users, and webhook events tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-09
"""

import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'remnawave_settings',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('base_url', sa.String(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('polling_enabled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('polling_interval_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('api_token', sa.String(), nullable=True),
        sa.Column('webhook_secret', sa.String(), nullable=True),
        sa.Column('subscription_url', sa.String(), nullable=True),
        sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_test_status', sa.String(), nullable=True),
        sa.Column('last_test_error', sa.String(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'remnawave_users',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('remnawave_uuid', sa.String(), nullable=False),
        sa.Column('remnawave_id', sa.Integer(), nullable=True),
        sa.Column('short_uuid', sa.String(), nullable=True),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('expire_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('tag', sa.String(), nullable=True),
        sa.Column('telegram_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('traffic_limit_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('traffic_limit_strategy', sa.String(), nullable=False, server_default='NO_RESET'),
        sa.Column('traffic_used_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('lifetime_used_traffic_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_traffic_reset_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('online_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_connected_node_uuid', sa.String(), nullable=True),
        sa.Column('hwid_device_limit', sa.Integer(), nullable=True),
        sa.Column('external_squad_uuid', sa.String(), nullable=True),
        sa.Column('active_internal_squads_json', sa.String(), nullable=True),
        sa.Column('subscription_url_encrypted', sa.String(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_error', sa.String(), nullable=True),
        sa.Column('delete_requested_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id'),
        sa.UniqueConstraint('remnawave_uuid'),
    )
    op.create_index('ix_remnawave_users_remnawave_uuid', 'remnawave_users', ['remnawave_uuid'])
    op.create_table(
        'remnawave_webhook_events',
        sa.Column('id', sa.String(), nullable=False, primary_key=True),
        sa.Column('event_key', sa.String(), nullable=False, unique=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('remnawave_user_uuid', sa.String(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('remnawave_webhook_events')
    op.drop_index('ix_remnawave_users_remnawave_uuid', table_name='remnawave_users')
    op.drop_table('remnawave_users')
    op.drop_table('remnawave_settings')
