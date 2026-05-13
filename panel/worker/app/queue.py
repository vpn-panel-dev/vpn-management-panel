from __future__ import annotations

import asyncio
import importlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.commands import WorkerCommand

MessageHandler = Callable[[WorkerCommand], Awaitable[None]]

EXCHANGE = 'amnezia.jobs'
DEAD_LETTER_EXCHANGE = 'amnezia.jobs.dlx'
SYNC_QUEUE = 'amnezia.sync'
PROVISION_QUEUE = 'amnezia.provision'
POISON_QUEUE = 'amnezia.poison'
RETRY_QUEUES = (
    ('amnezia.retry.10s', 10_000),
    ('amnezia.retry.1m', 60_000),
    ('amnezia.retry.10m', 600_000),
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3


class RabbitQueue:
    def __init__(self, url: str, retry_policy: RetryPolicy | None = None) -> None:
        self._url = url
        self._retry_policy = retry_policy or RetryPolicy()

    async def consume(self, handler: MessageHandler, concurrency: int) -> None:
        aio_pika = importlib.import_module('aio_pika')
        connection = await aio_pika.connect_robust(self._url)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=concurrency)
            exchange, dlx = await self._declare_topology(channel, aio_pika)
            queues = [
                await channel.declare_queue(SYNC_QUEUE, durable=True),
                await channel.declare_queue(PROVISION_QUEUE, durable=True),
            ]
            for queue in queues:
                await queue.bind(exchange, routing_key=queue.name)
            semaphore = asyncio.Semaphore(concurrency)

            async with asyncio.TaskGroup() as task_group:
                for queue in queues:
                    task_group.create_task(
                        self._consume_queue(queue, semaphore, handler, dlx, aio_pika)
                    )

    async def publish_command(self, command: WorkerCommand) -> None:
        aio_pika = importlib.import_module('aio_pika')
        connection = await aio_pika.connect_robust(self._url)
        async with connection:
            channel = await connection.channel()
            exchange, _ = await self._declare_topology(channel, aio_pika)
            await self._publish(exchange, aio_pika, command, self._routing_key(command))

    async def _consume_queue(
        self,
        queue: Any,
        semaphore: asyncio.Semaphore,
        handler: MessageHandler,
        dlx: Any,
        aio_pika: Any,
    ) -> None:
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await semaphore.acquire()
                task = asyncio.create_task(self._handle_message(message, handler, dlx, aio_pika))
                task.add_done_callback(lambda _task: semaphore.release())

    async def _handle_message(
        self,
        message: Any,
        handler: MessageHandler,
        dlx: Any,
        aio_pika: Any,
    ) -> None:
        body = json.loads(message.body.decode('utf-8'))
        command = WorkerCommand.model_validate(body)
        try:
            await handler(command)
        except Exception:
            await self._retry_or_dead_letter(command, message, dlx, aio_pika)
            await message.ack()
            return
        await message.ack()

    async def _declare_topology(self, channel: Any, aio_pika: Any) -> tuple[Any, Any]:
        exchange = await channel.declare_exchange(
            EXCHANGE,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        dlx = await channel.declare_exchange(
            DEAD_LETTER_EXCHANGE,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        poison_queue = await channel.declare_queue(POISON_QUEUE, durable=True)
        await poison_queue.bind(dlx, routing_key=POISON_QUEUE)
        for name, delay_ms in RETRY_QUEUES:
            queue = await channel.declare_queue(
                name,
                durable=True,
                arguments={
                    'x-message-ttl': delay_ms,
                    'x-dead-letter-exchange': EXCHANGE,
                },
            )
            await queue.bind(dlx, routing_key=name)
        return exchange, dlx

    async def _retry_or_dead_letter(
        self,
        command: WorkerCommand,
        message: Any,
        dlx: Any,
        aio_pika: Any,
    ) -> None:
        attempts = int((message.headers or {}).get('x-retry-count', 0)) + 1
        if attempts >= self._retry_policy.max_attempts:
            await self._publish(dlx, aio_pika, command, POISON_QUEUE, {'x-retry-count': attempts})
            return
        retry_queue = RETRY_QUEUES[min(attempts - 1, len(RETRY_QUEUES) - 1)][0]
        await self._publish(dlx, aio_pika, command, retry_queue, {'x-retry-count': attempts})

    async def _publish(
        self,
        exchange: Any,
        aio_pika: Any,
        command: WorkerCommand,
        routing_key: str,
        headers: dict[str, Any] | None = None,
    ) -> None:
        await exchange.publish(
            aio_pika.Message(
                body=command.model_dump_json().encode('utf-8'),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers=headers or {},
            ),
            routing_key=routing_key,
        )

    def _routing_key(self, command: WorkerCommand) -> str:
        if command.command == 'provision_node':
            return PROVISION_QUEUE
        return SYNC_QUEUE
