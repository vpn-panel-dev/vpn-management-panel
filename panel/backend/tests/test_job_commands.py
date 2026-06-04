from __future__ import annotations

import uuid

import pytest

from app.job_commands import (
    cleanup_raw_traffic_samples,
    provision_node,
    remnawave_disable_user,
    remnawave_full_reconcile,
    remnawave_sync_user,
    sync_all,
    sync_node,
)
from app.queue import REMNAWAVE_SYNC_USER_QUEUE, SYNC_NODE_QUEUE


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


@pytest.mark.asyncio
async def test_enqueue_uses_per_operation_routing_key(monkeypatch):
    published = []

    async def _publish(payload, routing_key: str, *, url: str | None = None) -> None:
        published.append((payload, routing_key, url))

    monkeypatch.setattr('app.job_commands.publish_command', _publish)

    from app.job_commands import enqueue_remnawave_sync_user, enqueue_sync_node

    await enqueue_sync_node('node-1', url='amqp://example/')
    await enqueue_remnawave_sync_user('user-1')

    assert published[0][0]['command'] == 'sync_node'
    assert published[0][1] == SYNC_NODE_QUEUE
    assert published[0][2] == 'amqp://example/'
    assert published[1][0]['command'] == 'remnawave_sync_user'
    assert published[1][1] == REMNAWAVE_SYNC_USER_QUEUE
