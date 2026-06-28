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
TELEGRAM_PROXY_OPERATIONS_QUEUE = 'amnezia.telegram_proxy_operations'
POISON_QUEUE = 'amnezia.poison'
RETRY_QUEUES = (
    ('amnezia.retry.10s', 10_000),
    ('amnezia.retry.1m', 60_000),
    ('amnezia.retry.10m', 600_000),
)
RETRY_DELAYS = (
    ('10s', 10_000),
    ('1m', 60_000),
    ('10m', 600_000),
)


@dataclass(frozen=True)
class QueueSpec:
    command: str
    queue_name: str
    sequential: bool


QUEUE_SPECS = (
    QueueSpec('sync_all', SYNC_ALL_QUEUE, True),
    QueueSpec('sync_node', SYNC_NODE_QUEUE, True),
    QueueSpec('provision_node', PROVISION_NODE_QUEUE, True),
    QueueSpec('health_check_all', NODE_HEARTBEAT_QUEUE, False),
    QueueSpec('health_check_node', NODE_HEARTBEAT_QUEUE, False),
    QueueSpec('cleanup_raw_traffic_samples', CLEANUP_RAW_TRAFFIC_SAMPLES_QUEUE, False),
    QueueSpec('remnawave_full_reconcile', REMNAWAVE_FULL_RECONCILE_QUEUE, False),
    QueueSpec('remnawave_sync_user', REMNAWAVE_SYNC_USER_QUEUE, False),
    QueueSpec('remnawave_disable_user', REMNAWAVE_DISABLE_USER_QUEUE, False),
    QueueSpec('telegram_proxy_apply_node', TELEGRAM_PROXY_OPERATIONS_QUEUE, True),
    QueueSpec('telegram_proxy_check_node', TELEGRAM_PROXY_OPERATIONS_QUEUE, True),
    QueueSpec('telegram_proxy_disable_node', TELEGRAM_PROXY_OPERATIONS_QUEUE, True),
)
ROUTING_KEYS = {spec.command: spec.queue_name for spec in QUEUE_SPECS}
LEGACY_QUEUE_NAMES = (LEGACY_SYNC_QUEUE, LEGACY_PROVISION_QUEUE)
SEQUENTIAL_QUEUE_ARGS = {'x-single-active-consumer': True}


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3


class RabbitQueue:
    def __init__(self, url: str, retry_policy: RetryPolicy | None = None) -> None:
        self._url = url
        self._retry_policy = retry_policy or RetryPolicy()
        self._publish_lock = asyncio.Lock()
        self._publish_connection: Any | None = None
        self._publish_channel: Any | None = None
        self._publish_exchange: Any | None = None

    async def consume(self, handler: MessageHandler, concurrency: int) -> None:
        aio_pika = importlib.import_module('aio_pika')
        connection = await aio_pika.connect_robust(self._url)
        async with connection:
            sequential_channel = await connection.channel()
            await sequential_channel.set_qos(prefetch_count=1)
            parallel_channel = await connection.channel()
            await parallel_channel.set_qos(prefetch_count=concurrency)
            sequential_exchange, sequential_dlx = await self._declare_topology(
                sequential_channel,
                aio_pika,
            )
            parallel_exchange, parallel_dlx = await self._declare_topology(
                parallel_channel,
                aio_pika,
            )
            sequential_queues = await self._declare_consumer_queues(
                sequential_channel,
                sequential_exchange,
                sequential=True,
            )
            parallel_queues = await self._declare_consumer_queues(
                parallel_channel,
                parallel_exchange,
                sequential=False,
            )
            sequential_limiter = asyncio.Semaphore(1)
            parallel_limiter = asyncio.Semaphore(concurrency)

            async with asyncio.TaskGroup() as task_group:
                for queue in sequential_queues:
                    task_group.create_task(
                        self._consume_queue(
                            queue,
                            sequential_limiter,
                            handler,
                            sequential_dlx,
                            aio_pika,
                        )
                    )
                for queue in parallel_queues:
                    task_group.create_task(
                        self._consume_queue(
                            queue,
                            parallel_limiter,
                            handler,
                            parallel_dlx,
                            aio_pika,
                        )
                    )

    async def publish_command(self, command: WorkerCommand) -> None:
        aio_pika = importlib.import_module('aio_pika')
        exchange = await self._publisher_exchange(aio_pika)
        await self._publish(exchange, aio_pika, command, self._routing_key(command))

    async def close(self) -> None:
        if self._publish_channel is not None and not getattr(
            self._publish_channel, 'is_closed', True
        ):
            await self._publish_channel.close()
        if self._publish_connection is not None and not getattr(
            self._publish_connection, 'is_closed', True
        ):
            await self._publish_connection.close()
        self._publish_channel = None
        self._publish_connection = None
        self._publish_exchange = None

    async def _declare_consumer_queues(
        self,
        channel: Any,
        exchange: Any,
        *,
        sequential: bool,
    ) -> list[Any]:
        queues = []
        declared_queue_names = set()
        for spec in QUEUE_SPECS:
            if spec.sequential is not sequential:
                continue
            if spec.queue_name in declared_queue_names:
                continue
            queue = await channel.declare_queue(
                spec.queue_name,
                durable=True,
                arguments=SEQUENTIAL_QUEUE_ARGS if spec.sequential else {},
            )
            await queue.bind(exchange, routing_key=spec.queue_name)
            queues.append(queue)
            declared_queue_names.add(spec.queue_name)
        if sequential:
            for legacy_queue_name in LEGACY_QUEUE_NAMES:
                queue = await channel.declare_queue(legacy_queue_name, durable=True)
                queues.append(queue)
        return queues

    async def _publisher_exchange(self, aio_pika: Any) -> Any:
        async with self._publish_lock:
            if self._publish_exchange is not None and not getattr(
                self._publish_exchange, 'is_closed', False
            ):
                return self._publish_exchange

            if self._publish_connection is None or getattr(
                self._publish_connection, 'is_closed', True
            ):
                self._publish_connection = await aio_pika.connect_robust(self._url)
            if self._publish_channel is None or getattr(self._publish_channel, 'is_closed', True):
                self._publish_channel = await self._publish_connection.channel()
                self._publish_exchange, _ = await self._declare_topology(
                    self._publish_channel,
                    aio_pika,
                )

            return self._publish_exchange

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
        declared_queue_names = set()
        for spec in QUEUE_SPECS:
            if spec.queue_name in declared_queue_names:
                continue
            queue = await channel.declare_queue(
                spec.queue_name,
                durable=True,
                arguments=SEQUENTIAL_QUEUE_ARGS if spec.sequential else {},
            )
            await queue.bind(exchange, routing_key=spec.queue_name)
            declared_queue_names.add(spec.queue_name)
        legacy_sync_queue = await channel.declare_queue(LEGACY_SYNC_QUEUE, durable=True)
        legacy_provision_queue = await channel.declare_queue(LEGACY_PROVISION_QUEUE, durable=True)
        await legacy_sync_queue.bind(exchange, routing_key='sync')
        await legacy_provision_queue.bind(exchange, routing_key='provision')
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
        for spec in QUEUE_SPECS:
            for delay_name, delay_ms in RETRY_DELAYS:
                name = self._retry_queue_name(spec.command, delay_name)
                if name in declared_queue_names:
                    continue
                queue = await channel.declare_queue(
                    name,
                    durable=True,
                    arguments={
                        'x-message-ttl': delay_ms,
                        'x-dead-letter-exchange': EXCHANGE,
                        'x-dead-letter-routing-key': spec.queue_name,
                    },
                )
                await queue.bind(dlx, routing_key=name)
                declared_queue_names.add(name)
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
        delay_name = RETRY_DELAYS[min(attempts - 1, len(RETRY_DELAYS) - 1)][0]
        retry_queue = self._retry_queue_name(command.command, delay_name)
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
        return ROUTING_KEYS[command.command]

    def _retry_queue_name(self, command: str, delay_name: str) -> str:
        return f'{ROUTING_KEYS[command]}.retry.{delay_name}'
