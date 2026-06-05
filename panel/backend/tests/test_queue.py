from __future__ import annotations

import json

from aio_pika import DeliveryMode

from app.queue import (
    COMMAND_QUEUES,
    DLX_NAME,
    EXCHANGE_NAME,
    LEGACY_PROVISION_QUEUE,
    LEGACY_SYNC_QUEUE,
    PROVISION_NODE_QUEUE,
    SEQUENTIAL_QUEUE_ARGS,
    SYNC_NODE_QUEUE,
    declare_topology,
    publish_command,
    retry_queue_for_command,
    routing_key_for_command,
)


class _FakeExchange:
    def __init__(self) -> None:
        self.published = []

    async def publish(self, message, routing_key: str, mandatory: bool) -> None:
        self.published.append((message, routing_key, mandatory))


class _FakeQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.bindings = []

    async def bind(self, exchange, routing_key: str) -> None:
        self.bindings.append((exchange, routing_key))


class _FakeChannel:
    def __init__(self) -> None:
        self.exchange = _FakeExchange()
        self.queues = {
            LEGACY_SYNC_QUEUE: _FakeQueue(LEGACY_SYNC_QUEUE),
            LEGACY_PROVISION_QUEUE: _FakeQueue(LEGACY_PROVISION_QUEUE),
        }
        self.queue_arguments = {}

    async def declare_exchange(self, name, exchange_type, durable: bool):
        assert name in {EXCHANGE_NAME, DLX_NAME}
        assert durable is True
        return self.exchange

    async def declare_queue(self, name, durable: bool, arguments: dict):
        assert durable is True
        self.queue_arguments[name] = arguments
        return self.queues.setdefault(name, _FakeQueue(name))


class _FakeConnection:
    def __init__(self) -> None:
        self.channel_obj = _FakeChannel()
        self.closed = False

    async def channel(self, publisher_confirms: bool):
        assert publisher_confirms is True
        return self.channel_obj

    async def close(self) -> None:
        self.closed = True


def test_publish_command_is_lazy_and_persistent(monkeypatch):
    connection = _FakeConnection()
    connect_calls = 0

    async def _fake_connect(_):
        nonlocal connect_calls
        connect_calls += 1
        return connection

    monkeypatch.setattr('app.queue.connect_robust', _fake_connect)

    payload = {
        'command': 'sync_all',
        'idempotency_key': '1a2f2df8-9d96-4e7d-a6e2-0bd5c8b5b6b1',
        'operation_id': '5e31b8ff-90ff-4b0c-a2cd-0c3d1c5f8f68',
        'target_type': 'all',
        'target_id': None,
        'created_at': '2026-05-08T00:00:00+00:00',
    }

    import asyncio

    asyncio.run(publish_command(payload, 'sync', url='amqp://example/'))
    asyncio.run(publish_command(payload, 'sync', url='amqp://example/'))

    assert connect_calls == 1
    assert connection.closed is False
    assert len(connection.channel_obj.exchange.published) == 2
    message, routing_key, mandatory = connection.channel_obj.exchange.published[0]
    assert routing_key == 'sync'
    assert mandatory is True
    assert message.delivery_mode == DeliveryMode.PERSISTENT
    assert message.content_type == 'application/json'
    assert json.loads(message.body.decode()) == payload


def test_declares_per_command_queues_with_legacy_bindings():
    import asyncio

    channel = _FakeChannel()

    asyncio.run(declare_topology(channel))

    assert {queue.queue_name for queue in COMMAND_QUEUES}.issubset(channel.queues)
    assert channel.queues[LEGACY_SYNC_QUEUE].bindings == [(channel.exchange, 'sync')]
    assert channel.queues[LEGACY_PROVISION_QUEUE].bindings == [(channel.exchange, 'provision')]
    assert channel.queues[SYNC_NODE_QUEUE].bindings == [(channel.exchange, SYNC_NODE_QUEUE)]
    assert channel.queues[PROVISION_NODE_QUEUE].bindings == [
        (channel.exchange, PROVISION_NODE_QUEUE)
    ]
    assert channel.queue_arguments[SYNC_NODE_QUEUE] == SEQUENTIAL_QUEUE_ARGS
    assert channel.queue_arguments[PROVISION_NODE_QUEUE] == SEQUENTIAL_QUEUE_ARGS
    assert channel.queue_arguments[LEGACY_SYNC_QUEUE] == {}
    sync_node_retry = retry_queue_for_command('sync_node', '10s')
    assert channel.queue_arguments[sync_node_retry] == {
        'x-message-ttl': 10_000,
        'x-dead-letter-exchange': EXCHANGE_NAME,
        'x-dead-letter-routing-key': SYNC_NODE_QUEUE,
    }


def test_routing_key_for_command_uses_per_operation_queue():
    assert routing_key_for_command('sync_node') == SYNC_NODE_QUEUE
    assert routing_key_for_command('sync_all') == SYNC_NODE_QUEUE
    assert routing_key_for_command('provision_node') == PROVISION_NODE_QUEUE
    assert routing_key_for_command('sync_node') == routing_key_for_command('provision_node')
