from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from app.backend_client import BackendClient, command_from_operation
from app.commands import CommandName, WorkerCommand
from app.handlers import CommandHandler
from app.node_client import NodeClient
from app.queue import RabbitQueue

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    rabbitmq_url: str
    backend_internal_url: str
    worker_token: str
    sync_interval_sec: float = 30.0
    worker_concurrency: int = 4
    recovery_interval_sec: float = 30.0
    stale_after_sec: int = 30

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            rabbitmq_url=_required_env('RABBITMQ_URL'),
            backend_internal_url=_required_env('BACKEND_INTERNAL_URL'),
            worker_token=_required_env('WORKER_TOKEN'),
            sync_interval_sec=float(os.getenv('SYNC_INTERVAL_SEC', '30')),
            worker_concurrency=int(os.getenv('WORKER_CONCURRENCY', '4')),
            recovery_interval_sec=float(os.getenv('RECOVERY_INTERVAL_SEC', '30')),
            stale_after_sec=int(os.getenv('STALE_AFTER_SEC', '30')),
        )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'{name} is required')
    return value


async def run(settings: Settings) -> None:
    backend = BackendClient(settings.backend_internal_url, settings.worker_token)
    command_handler = CommandHandler(backend, NodeClient())
    queue = RabbitQueue(settings.rabbitmq_url)

    async def handle_queue_command(command):
        await command_handler.handle(command)

    async with asyncio.TaskGroup() as task_group:
        task_group.create_task(queue.consume(handle_queue_command, settings.worker_concurrency))
        task_group.create_task(schedule_sync_all(queue, settings.sync_interval_sec))
        task_group.create_task(
            schedule_cleanup_raw_traffic_samples(queue, settings.sync_interval_sec)
        )
        task_group.create_task(schedule_remnawave_reconcile(backend, queue))
        task_group.create_task(recover_stale_operations(backend, queue, settings))


async def schedule_sync_all(queue: RabbitQueue, interval_sec: float) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        await queue.publish_command(_new_command('sync_all', 'all', None))


async def schedule_cleanup_raw_traffic_samples(queue: RabbitQueue, interval_sec: float) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        await queue.publish_command(_new_command('cleanup_raw_traffic_samples', 'traffic', None))


async def schedule_remnawave_reconcile(
    backend: BackendClient,
    queue: RabbitQueue,
    interval_sec: float = 60.0,
) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        try:
            state = await backend.fetch_remnawave_polling_state()
            if state.get('enabled') and state.get('due'):
                await queue.publish_command(
                    _new_command('remnawave_full_reconcile', 'remnawave', None)
                )
        except Exception:
            log.exception('Failed to schedule Remnawave reconcile')
            continue


async def recover_stale_operations(
    backend: BackendClient,
    queue: RabbitQueue,
    settings: Settings,
) -> None:
    while True:
        await asyncio.sleep(settings.recovery_interval_sec)
        operations = await backend.fetch_stale_operations(
            status='queued',
            older_than_seconds=settings.stale_after_sec,
        )
        for operation in operations:
            await queue.publish_command(command_from_operation(operation))


def _new_command(command: CommandName, target_type: str, target_id: str | None) -> WorkerCommand:
    operation_id = str(uuid4())
    return WorkerCommand.model_validate(
        {
            'command': command,
            'idempotency_key': operation_id,
            'operation_id': operation_id,
            'target_type': target_type,
            'target_id': target_id,
            'created_at': datetime.now(UTC).isoformat(),
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Run the standalone panel worker.')
    parser.add_argument(
        '--check-config',
        action='store_true',
        help='validate required environment variables and exit',
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.check_config:
        Settings.from_env()
        return

    asyncio.run(run(Settings.from_env()))


if __name__ == '__main__':
    main()
