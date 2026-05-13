from __future__ import annotations

import json

from aio_pika import DeliveryMode

from app.queue import DLX_NAME, EXCHANGE_NAME, PROVISION_QUEUE, SYNC_QUEUE, publish_command


class _FakeExchange:
    def __init__(self) -> None:
        self.published = []

    async def publish(self, message, routing_key: str, mandatory: bool) -> None:
        self.published.append((message, routing_key, mandatory))


class _FakeQueue:
    def __init__(self) -> None:
        self.bindings = []

    async def bind(self, exchange, routing_key: str) -> None:
        self.bindings.append((exchange, routing_key))


class _FakeChannel:
    def __init__(self) -> None:
        self.exchange = _FakeExchange()
        self.queues = {
            SYNC_QUEUE: _FakeQueue(),
            PROVISION_QUEUE: _FakeQueue(),
        }

    async def declare_exchange(self, name, exchange_type, durable: bool):
        assert name in {EXCHANGE_NAME, DLX_NAME}
        assert durable is True
        return self.exchange

    async def declare_queue(self, name, durable: bool, arguments: dict):
        assert durable is True
        return self.queues.setdefault(name, _FakeQueue())


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

    async def _fake_connect(_):
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

    assert connection.closed is True
    message, routing_key, mandatory = connection.channel_obj.exchange.published[0]
    assert routing_key == 'sync'
    assert mandatory is True
    assert message.delivery_mode == DeliveryMode.PERSISTENT
    assert message.content_type == 'application/json'
    assert json.loads(message.body.decode()) == payload
