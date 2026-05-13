from __future__ import annotations

import json
import os
from collections.abc import Mapping
from importlib import import_module
from typing import Any

_aio_pika = import_module('aio_pika')
DeliveryMode = _aio_pika.DeliveryMode
ExchangeType = _aio_pika.ExchangeType
Message = _aio_pika.Message
connect_robust = _aio_pika.connect_robust

EXCHANGE_NAME = 'amnezia.jobs'
DLX_NAME = 'amnezia.jobs.dlx'

SYNC_QUEUE = 'amnezia.sync'
PROVISION_QUEUE = 'amnezia.provision'
RETRY_10S_QUEUE = 'amnezia.retry.10s'
RETRY_1M_QUEUE = 'amnezia.retry.1m'
RETRY_10M_QUEUE = 'amnezia.retry.10m'
POISON_QUEUE = 'amnezia.poison'

SYNC_ROUTING_KEY = 'sync'
PROVISION_ROUTING_KEY = 'provision'

QUEUE_ARGS = {}
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

    sync_queue = await channel.declare_queue(SYNC_QUEUE, durable=True, arguments=QUEUE_ARGS)
    provision_queue = await channel.declare_queue(
        PROVISION_QUEUE,
        durable=True,
        arguments=QUEUE_ARGS,
    )
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
    poison_queue = await channel.declare_queue(POISON_QUEUE, durable=True, arguments=POISON_ARGS)

    await sync_queue.bind(exchange, routing_key=SYNC_ROUTING_KEY)
    await provision_queue.bind(exchange, routing_key=PROVISION_ROUTING_KEY)
    await retry_10s.bind(dlx, routing_key=RETRY_10S_QUEUE)
    await retry_1m.bind(dlx, routing_key=RETRY_1M_QUEUE)
    await retry_10m.bind(dlx, routing_key=RETRY_10M_QUEUE)
    await poison_queue.bind(dlx, routing_key=POISON_QUEUE)

    return {
        'exchange': exchange,
        'dlx': dlx,
        'queues': {
            'sync': sync_queue,
            'provision': provision_queue,
            'retry_10s': retry_10s,
            'retry_1m': retry_1m,
            'retry_10m': retry_10m,
            'poison': poison_queue,
        },
    }


async def publish_command(
    payload: Mapping[str, Any],
    routing_key: str,
    *,
    url: str | None = None,
) -> None:
    connection = await connect_robust(_rabbitmq_url(url))
    try:
        channel = await connection.channel(publisher_confirms=True)
        topology = await declare_topology(channel)
        message = Message(
            body=_message_body(payload),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type='application/json',
        )
        await topology['exchange'].publish(message, routing_key=routing_key, mandatory=True)
    finally:
        await connection.close()
