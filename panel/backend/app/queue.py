from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Any

_aio_pika = import_module('aio_pika')
DeliveryMode = _aio_pika.DeliveryMode
ExchangeType = _aio_pika.ExchangeType
Message = _aio_pika.Message
connect_robust = _aio_pika.connect_robust

EXCHANGE_NAME = 'amnezia.jobs'
DLX_NAME = 'amnezia.jobs.dlx'

LEGACY_SYNC_QUEUE = 'amnezia.sync'
LEGACY_PROVISION_QUEUE = 'amnezia.provision'
SYNC_QUEUE = LEGACY_SYNC_QUEUE
PROVISION_QUEUE = LEGACY_PROVISION_QUEUE
NODE_OPERATIONS_QUEUE = 'amnezia.node_operations'
SYNC_ALL_QUEUE = NODE_OPERATIONS_QUEUE
SYNC_NODE_QUEUE = NODE_OPERATIONS_QUEUE
PROVISION_NODE_QUEUE = NODE_OPERATIONS_QUEUE
NODE_HEARTBEAT_QUEUE = 'amnezia.node_heartbeat'
CLEANUP_RAW_TRAFFIC_SAMPLES_QUEUE = 'amnezia.cleanup_raw_traffic_samples'
REMNAWAVE_FULL_RECONCILE_QUEUE = 'amnezia.remnawave_full_reconcile'
REMNAWAVE_SYNC_USER_QUEUE = 'amnezia.remnawave_sync_user'
REMNAWAVE_DISABLE_USER_QUEUE = 'amnezia.remnawave_disable_user'
RETRY_10S_QUEUE = 'amnezia.retry.10s'
RETRY_1M_QUEUE = 'amnezia.retry.1m'
RETRY_10M_QUEUE = 'amnezia.retry.10m'
POISON_QUEUE = 'amnezia.poison'
RETRY_DELAYS = (
    ('10s', 10_000),
    ('1m', 60_000),
    ('10m', 600_000),
)

SYNC_ROUTING_KEY = 'sync'
PROVISION_ROUTING_KEY = 'provision'


@dataclass(frozen=True)
class CommandQueue:
    command: str
    queue_name: str
    sequential: bool = False


COMMAND_QUEUES = (
    CommandQueue('sync_all', SYNC_ALL_QUEUE, sequential=True),
    CommandQueue('sync_node', SYNC_NODE_QUEUE, sequential=True),
    CommandQueue('provision_node', PROVISION_NODE_QUEUE, sequential=True),
    CommandQueue('health_check_all', NODE_HEARTBEAT_QUEUE),
    CommandQueue('health_check_node', NODE_HEARTBEAT_QUEUE),
    CommandQueue('cleanup_raw_traffic_samples', CLEANUP_RAW_TRAFFIC_SAMPLES_QUEUE),
    CommandQueue('remnawave_full_reconcile', REMNAWAVE_FULL_RECONCILE_QUEUE),
    CommandQueue('remnawave_sync_user', REMNAWAVE_SYNC_USER_QUEUE),
    CommandQueue('remnawave_disable_user', REMNAWAVE_DISABLE_USER_QUEUE),
)
COMMAND_ROUTING_KEYS = {queue.command: queue.queue_name for queue in COMMAND_QUEUES}

QUEUE_ARGS = {}
SEQUENTIAL_QUEUE_ARGS = {'x-single-active-consumer': True}
RETRY_10S_ARGS = {
    'x-message-ttl': 10_000,
    'x-dead-letter-exchange': EXCHANGE_NAME,
}
RETRY_1M_ARGS = {
    'x-message-ttl': 60_000,
    'x-dead-letter-exchange': EXCHANGE_NAME,
}
RETRY_10M_ARGS = {
    'x-message-ttl': 600_000,
    'x-dead-letter-exchange': EXCHANGE_NAME,
}
POISON_ARGS = {}


@dataclass
class PublisherState:
    lock: asyncio.Lock
    connection: Any | None = None
    channel: Any | None = None
    exchange: Any | None = None


_publisher_state = PublisherState(lock=asyncio.Lock())


def _rabbitmq_url(url: str | None = None) -> str:
    return (
        url
        or os.environ.get('RABBITMQ_URL')
        or os.environ.get('AMQP_URL')
        or 'amqp://guest:guest@localhost/'
    )


def _message_body(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


async def declare_topology(channel: Any) -> dict[str, Any]:
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
    dlx = await channel.declare_exchange(DLX_NAME, ExchangeType.DIRECT, durable=True)

    legacy_sync_queue = await channel.declare_queue(
        LEGACY_SYNC_QUEUE,
        durable=True,
        arguments=QUEUE_ARGS,
    )
    legacy_provision_queue = await channel.declare_queue(
        LEGACY_PROVISION_QUEUE,
        durable=True,
        arguments=QUEUE_ARGS,
    )
    declared_queues = {}
    command_queues = {}
    for command_queue in COMMAND_QUEUES:
        queue = declared_queues.get(command_queue.queue_name)
        if queue is None:
            queue = await channel.declare_queue(
                command_queue.queue_name,
                durable=True,
                arguments=SEQUENTIAL_QUEUE_ARGS if command_queue.sequential else QUEUE_ARGS,
            )
            declared_queues[command_queue.queue_name] = queue
        command_queues[command_queue.command] = queue
    retry_10s = await channel.declare_queue(
        RETRY_10S_QUEUE,
        durable=True,
        arguments=RETRY_10S_ARGS,
    )
    retry_1m = await channel.declare_queue(
        RETRY_1M_QUEUE,
        durable=True,
        arguments=RETRY_1M_ARGS,
    )
    retry_10m = await channel.declare_queue(
        RETRY_10M_QUEUE,
        durable=True,
        arguments=RETRY_10M_ARGS,
    )
    command_retry_queues = {}
    for command_queue in COMMAND_QUEUES:
        for delay_name, delay_ms in RETRY_DELAYS:
            retry_queue_name = retry_queue_for_command(command_queue.command, delay_name)
            if retry_queue_name in command_retry_queues:
                continue
            command_retry_queues[retry_queue_name] = await channel.declare_queue(
                retry_queue_name,
                durable=True,
                arguments={
                    'x-message-ttl': delay_ms,
                    'x-dead-letter-exchange': EXCHANGE_NAME,
                    'x-dead-letter-routing-key': command_queue.queue_name,
                },
            )
    poison_queue = await channel.declare_queue(POISON_QUEUE, durable=True, arguments=POISON_ARGS)

    await legacy_sync_queue.bind(exchange, routing_key=SYNC_ROUTING_KEY)
    await legacy_provision_queue.bind(exchange, routing_key=PROVISION_ROUTING_KEY)
    for queue_name, queue in declared_queues.items():
        await queue.bind(exchange, routing_key=queue_name)
    await retry_10s.bind(dlx, routing_key=RETRY_10S_QUEUE)
    await retry_1m.bind(dlx, routing_key=RETRY_1M_QUEUE)
    await retry_10m.bind(dlx, routing_key=RETRY_10M_QUEUE)
    for retry_queue_name, retry_queue in command_retry_queues.items():
        await retry_queue.bind(dlx, routing_key=retry_queue_name)
    await poison_queue.bind(dlx, routing_key=POISON_QUEUE)

    return {
        'exchange': exchange,
        'dlx': dlx,
        'queues': {
            'legacy_sync': legacy_sync_queue,
            'legacy_provision': legacy_provision_queue,
            **command_queues,
            'retry_10s': retry_10s,
            'retry_1m': retry_1m,
            'retry_10m': retry_10m,
            **command_retry_queues,
            'poison': poison_queue,
        },
    }


def routing_key_for_command(command: str) -> str:
    return COMMAND_ROUTING_KEYS[command]


def retry_queue_for_command(command: str, delay_name: str) -> str:
    return f'{routing_key_for_command(command)}.retry.{delay_name}'


async def publish_command(
    payload: Mapping[str, Any],
    routing_key: str,
    *,
    url: str | None = None,
) -> None:
    exchange = await _publisher_exchange_for_url(url)
    message = Message(
        body=_message_body(payload),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type='application/json',
    )
    await exchange.publish(message, routing_key=routing_key, mandatory=True)


async def _publisher_exchange_for_url(url: str | None = None) -> Any:
    async with _publisher_state.lock:
        exchange = _publisher_state.exchange
        if exchange is not None and not getattr(exchange, 'is_closed', False):
            return exchange

        channel = _publisher_state.channel
        if channel is None or getattr(channel, 'is_closed', True):
            connection = _publisher_state.connection
            if connection is None or getattr(connection, 'is_closed', True):
                connection = await connect_robust(_rabbitmq_url(url))
                _publisher_state.connection = connection
            channel = await connection.channel(publisher_confirms=True)
            _publisher_state.channel = channel
            topology = await declare_topology(channel)
            _publisher_state.exchange = topology['exchange']

        return _publisher_state.exchange
