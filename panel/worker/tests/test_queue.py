from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.commands import WorkerCommand
from app.queue import (
    CLEANUP_RAW_TRAFFIC_SAMPLES_QUEUE,
    LEGACY_PROVISION_QUEUE,
    LEGACY_SYNC_QUEUE,
    NODE_HEARTBEAT_QUEUE,
    PROVISION_NODE_QUEUE,
    QUEUE_SPECS,
    REMNAWAVE_FULL_RECONCILE_QUEUE,
    SEQUENTIAL_QUEUE_ARGS,
    SYNC_NODE_QUEUE,
    TELEGRAM_PROXY_OPERATIONS_QUEUE,
    RabbitQueue,
)


class _FakeQueue:
    def __init__(self, name: str) -> None:
        self.name = name
        self.bindings = []

    async def bind(self, exchange, routing_key: str) -> None:
        self.bindings.append((exchange, routing_key))


class _FakeExchange:
    pass


class _FakeAioPika:
    class ExchangeType:
        DIRECT = 'direct'


class _FakeChannel:
    def __init__(self) -> None:
        self.exchange = _FakeExchange()
        self.dlx = _FakeExchange()
        self.queues: dict[str, _FakeQueue] = {}
        self.queue_arguments: dict[str, dict] = {}

    async def declare_exchange(self, name: str, exchange_type: str, durable: bool):
        _ = exchange_type
        assert durable is True
        if name.endswith('.dlx'):
            return self.dlx
        return self.exchange

    async def declare_queue(self, name: str, durable: bool, arguments: dict | None = None):
        assert durable is True
        self.queue_arguments[name] = arguments or {}
        return self.queues.setdefault(name, _FakeQueue(name))


def _command(command: str) -> WorkerCommand:
    target_id = (
        'node-1'
        if command
        in {
            'sync_node',
            'provision_node',
            'telegram_proxy_apply_node',
            'telegram_proxy_check_node',
            'telegram_proxy_disable_node',
        }
        else None
    )
    if command.startswith('telegram_proxy_'):
        target_type = 'telegram_proxy_node'
    elif target_id:
        target_type = 'node'
    else:
        target_type = 'all'
    return WorkerCommand.model_validate(
        {
            'command': command,
            'idempotency_key': f'idem-{command}',
            'operation_id': f'op-{command}',
            'track_operation': True,
            'target_type': target_type,
            'target_id': target_id,
            'created_at': datetime.now(UTC).isoformat(),
        }
    )


def test_worker_routing_key_uses_per_operation_queue() -> None:
    queue = RabbitQueue('amqp://example/')

    assert queue._routing_key(_command('sync_node')) == SYNC_NODE_QUEUE
    assert queue._routing_key(_command('sync_all')) == SYNC_NODE_QUEUE
    assert queue._routing_key(_command('provision_node')) == PROVISION_NODE_QUEUE
    assert queue._routing_key(_command('health_check_all')) == NODE_HEARTBEAT_QUEUE
    assert queue._routing_key(_command('cleanup_raw_traffic_samples')) == (
        CLEANUP_RAW_TRAFFIC_SAMPLES_QUEUE
    )
    assert queue._routing_key(_command('remnawave_full_reconcile')) == (
        REMNAWAVE_FULL_RECONCILE_QUEUE
    )
    assert queue._routing_key(_command('telegram_proxy_apply_node')) == (
        TELEGRAM_PROXY_OPERATIONS_QUEUE
    )
    assert queue._routing_key(_command('telegram_proxy_check_node')) == (
        TELEGRAM_PROXY_OPERATIONS_QUEUE
    )
    assert queue._routing_key(_command('telegram_proxy_disable_node')) == (
        TELEGRAM_PROXY_OPERATIONS_QUEUE
    )


def test_worker_declares_per_command_and_legacy_queues() -> None:
    queue = RabbitQueue('amqp://example/')
    channel = _FakeChannel()

    asyncio.run(queue._declare_topology(channel, _FakeAioPika()))

    assert {spec.queue_name for spec in QUEUE_SPECS}.issubset(channel.queues)
    assert channel.queues[SYNC_NODE_QUEUE].bindings == [(channel.exchange, SYNC_NODE_QUEUE)]
    assert channel.queues[PROVISION_NODE_QUEUE].bindings == [
        (channel.exchange, PROVISION_NODE_QUEUE)
    ]
    assert channel.queues[LEGACY_SYNC_QUEUE].bindings == [(channel.exchange, 'sync')]
    assert channel.queues[LEGACY_PROVISION_QUEUE].bindings == [(channel.exchange, 'provision')]
    assert channel.queue_arguments[SYNC_NODE_QUEUE] == SEQUENTIAL_QUEUE_ARGS
    assert channel.queue_arguments[PROVISION_NODE_QUEUE] == SEQUENTIAL_QUEUE_ARGS
    assert channel.queue_arguments[TELEGRAM_PROXY_OPERATIONS_QUEUE] == SEQUENTIAL_QUEUE_ARGS
    assert channel.queue_arguments[LEGACY_SYNC_QUEUE] == {}

    for delay_name, delay_ms in (('10s', 10_000), ('1m', 60_000), ('10m', 600_000)):
        retry_queue = f'{TELEGRAM_PROXY_OPERATIONS_QUEUE}.retry.{delay_name}'
        assert channel.queue_arguments[retry_queue] == {
            'x-message-ttl': delay_ms,
            'x-dead-letter-exchange': 'amnezia.jobs',
            'x-dead-letter-routing-key': TELEGRAM_PROXY_OPERATIONS_QUEUE,
        }


def test_worker_consumer_splits_sequential_and_parallel_queues() -> None:
    queue = RabbitQueue('amqp://example/')
    channel = _FakeChannel()

    sequential = asyncio.run(
        queue._declare_consumer_queues(channel, channel.exchange, sequential=True)
    )
    parallel = asyncio.run(
        queue._declare_consumer_queues(channel, channel.exchange, sequential=False)
    )

    assert [item.name for item in sequential] == [
        SYNC_NODE_QUEUE,
        TELEGRAM_PROXY_OPERATIONS_QUEUE,
        LEGACY_SYNC_QUEUE,
        LEGACY_PROVISION_QUEUE,
    ]
    assert [item.name for item in parallel] == [
        NODE_HEARTBEAT_QUEUE,
        CLEANUP_RAW_TRAFFIC_SAMPLES_QUEUE,
        REMNAWAVE_FULL_RECONCILE_QUEUE,
        'amnezia.remnawave_sync_user',
        'amnezia.remnawave_disable_user',
    ]
