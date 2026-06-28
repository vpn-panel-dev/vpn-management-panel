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
    telegram_proxy_apply_node,
    telegram_proxy_check_node,
    telegram_proxy_disable_node,
)
from app.queue import REMNAWAVE_SYNC_USER_QUEUE, SYNC_NODE_QUEUE, TELEGRAM_PROXY_OPERATIONS_QUEUE

EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD = {
    'command': 'telegram_proxy_apply_node',
    'idempotency_key': 'idem-telegram-proxy-apply',
    'operation_id': 'op-telegram-proxy-apply',
    'track_operation': True,
    'target_type': 'telegram_proxy_node',
    'target_id': 'node-apply',
    'created_at': '2026-06-27T12:00:00+00:00',
}

EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD = {
    'command': 'telegram_proxy_check_node',
    'idempotency_key': 'idem-telegram-proxy-check',
    'operation_id': 'op-telegram-proxy-check',
    'track_operation': True,
    'target_type': 'telegram_proxy_node',
    'target_id': 'node-check',
    'created_at': '2026-06-27T12:05:00+00:00',
}

EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD = {
    'command': 'telegram_proxy_disable_node',
    'idempotency_key': 'idem-telegram-proxy-disable',
    'operation_id': 'op-telegram-proxy-disable',
    'track_operation': True,
    'target_type': 'telegram_proxy_node',
    'target_id': 'node-disable',
    'created_at': '2026-06-27T12:10:00+00:00',
}


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
    assert payload['track_operation'] is True
    assert payload['target_type'] == 'remnawave'
    assert payload['target_id'] is None
    uuid.UUID(payload['idempotency_key'])
    uuid.UUID(payload['operation_id'])
    assert payload['created_at'].endswith('+00:00')


def test_cleanup_raw_traffic_samples_payload_shape():
    payload = cleanup_raw_traffic_samples()

    assert payload['command'] == 'cleanup_raw_traffic_samples'
    assert payload['track_operation'] is True
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


def test_telegram_proxy_node_payload_shapes():
    apply_payload = telegram_proxy_apply_node(
        'node-apply',
        idempotency_key=EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD['idempotency_key'],
        operation_id=EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD['operation_id'],
        created_at=EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD['created_at'],
    )
    check_payload = telegram_proxy_check_node(
        'node-check',
        idempotency_key=EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD['idempotency_key'],
        operation_id=EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD['operation_id'],
        created_at=EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD['created_at'],
    )
    disable_payload = telegram_proxy_disable_node(
        'node-disable',
        idempotency_key=EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD['idempotency_key'],
        operation_id=EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD['operation_id'],
        created_at=EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD['created_at'],
    )

    assert apply_payload == EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD
    assert check_payload == EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD
    assert disable_payload == EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD


@pytest.mark.asyncio
async def test_enqueue_uses_per_operation_routing_key(monkeypatch):
    published = []

    async def _publish(payload, routing_key: str, *, url: str | None = None) -> None:
        published.append((payload, routing_key, url))

    monkeypatch.setattr('app.job_commands.publish_command', _publish)

    from app.job_commands import (
        enqueue_remnawave_sync_user,
        enqueue_sync_node,
        enqueue_telegram_proxy_apply_node,
        enqueue_telegram_proxy_check_node,
        enqueue_telegram_proxy_disable_node,
    )

    await enqueue_sync_node('node-1', url='amqp://example/')
    await enqueue_remnawave_sync_user('user-1')
    apply_payload = await enqueue_telegram_proxy_apply_node(
        'node-apply',
        idempotency_key=EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD['idempotency_key'],
        operation_id=EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD['operation_id'],
        created_at=EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD['created_at'],
    )
    check_payload = await enqueue_telegram_proxy_check_node(
        'node-check',
        idempotency_key=EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD['idempotency_key'],
        operation_id=EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD['operation_id'],
        created_at=EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD['created_at'],
    )
    disable_payload = await enqueue_telegram_proxy_disable_node(
        'node-disable',
        idempotency_key=EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD['idempotency_key'],
        operation_id=EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD['operation_id'],
        created_at=EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD['created_at'],
    )

    assert published[0][0]['command'] == 'sync_node'
    assert published[0][1] == SYNC_NODE_QUEUE
    assert published[0][2] == 'amqp://example/'
    assert published[1][0]['command'] == 'remnawave_sync_user'
    assert published[1][1] == REMNAWAVE_SYNC_USER_QUEUE
    assert apply_payload == EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD
    assert check_payload == EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD
    assert disable_payload == EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD
    assert published[2] == (
        EXPECTED_TELEGRAM_PROXY_APPLY_PAYLOAD,
        TELEGRAM_PROXY_OPERATIONS_QUEUE,
        None,
    )
    assert published[3] == (
        EXPECTED_TELEGRAM_PROXY_CHECK_PAYLOAD,
        TELEGRAM_PROXY_OPERATIONS_QUEUE,
        None,
    )
    assert published[4] == (
        EXPECTED_TELEGRAM_PROXY_DISABLE_PAYLOAD,
        TELEGRAM_PROXY_OPERATIONS_QUEUE,
        None,
    )
