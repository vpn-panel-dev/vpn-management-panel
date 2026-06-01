from __future__ import annotations

import uuid

from app.job_commands import (
    cleanup_raw_traffic_samples,
    provision_node,
    remnawave_disable_user,
    remnawave_full_reconcile,
    remnawave_sync_user,
    sync_all,
    sync_node,
)


def test_sync_all_payload_shape():
    payload = sync_all()

    assert payload['command'] == 'sync_all'
    assert payload['target_type'] == 'all'
    assert payload['target_id'] is None
    uuid.UUID(payload['idempotency_key'])
    uuid.UUID(payload['operation_id'])
    assert payload['created_at'].endswith('+00:00')


def test_node_payload_shapes():
    sync_payload = sync_node('node-1')
    provision_payload = provision_node('node-2')

    assert sync_payload['command'] == 'sync_node'
    assert sync_payload['target_type'] == 'node'
    assert sync_payload['target_id'] == 'node-1'
    assert provision_payload['command'] == 'provision_node'
    assert provision_payload['target_type'] == 'node'
    assert provision_payload['target_id'] == 'node-2'


def test_remnawave_full_reconcile_payload_shape():
    payload = remnawave_full_reconcile()

    assert payload['command'] == 'remnawave_full_reconcile'
    assert payload['target_type'] == 'remnawave'
    assert payload['target_id'] is None
    uuid.UUID(payload['idempotency_key'])
    uuid.UUID(payload['operation_id'])
    assert payload['created_at'].endswith('+00:00')


def test_cleanup_raw_traffic_samples_payload_shape():
    payload = cleanup_raw_traffic_samples()

    assert payload['command'] == 'cleanup_raw_traffic_samples'
    assert payload['target_type'] == 'traffic'
    assert payload['target_id'] is None
    uuid.UUID(payload['idempotency_key'])
    uuid.UUID(payload['operation_id'])
    assert payload['created_at'].endswith('+00:00')


def test_remnawave_sync_user_payload_shape():
    payload = remnawave_sync_user('user-123')

    assert payload['command'] == 'remnawave_sync_user'
    assert payload['target_type'] == 'remnawave_user'
    assert payload['target_id'] == 'user-123'
    uuid.UUID(payload['idempotency_key'])
    uuid.UUID(payload['operation_id'])
    assert payload['created_at'].endswith('+00:00')


def test_remnawave_disable_user_payload_shape():
    payload = remnawave_disable_user('user-123')

    assert payload['command'] == 'remnawave_disable_user'
    assert payload['target_type'] == 'remnawave_user'
    assert payload['target_id'] == 'user-123'
    uuid.UUID(payload['idempotency_key'])
    uuid.UUID(payload['operation_id'])
    assert payload['created_at'].endswith('+00:00')
