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
    heartbeat_interval_sec: float = 5.0
    recovery_interval_sec: float = 30.0
    stale_after_sec: int = 30
    running_timeout_sec: int = 300
    provision_recovery_interval_sec: float = 60.0
    provision_pending_retry_sec: int = 60
    provision_failed_retry_sec: int = 300

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            rabbitmq_url=_required_env('RABBITMQ_URL'),
            backend_internal_url=_required_env('BACKEND_INTERNAL_URL'),
            worker_token=_required_env('WORKER_TOKEN'),
            sync_interval_sec=float(os.getenv('SYNC_INTERVAL_SEC', '30')),
            worker_concurrency=int(os.getenv('WORKER_CONCURRENCY', '4')),
            heartbeat_interval_sec=float(os.getenv('NODE_HEARTBEAT_INTERVAL_SEC', '5')),
            recovery_interval_sec=float(os.getenv('RECOVERY_INTERVAL_SEC', '30')),
            stale_after_sec=int(os.getenv('STALE_AFTER_SEC', '30')),
            running_timeout_sec=int(os.getenv('RUNNING_TIMEOUT_SEC', '300')),
            provision_recovery_interval_sec=float(
                os.getenv('PROVISION_RECOVERY_INTERVAL_SEC', '60')
            ),
            provision_pending_retry_sec=int(os.getenv('PROVISION_PENDING_RETRY_SEC', '60')),
            provision_failed_retry_sec=int(os.getenv('PROVISION_FAILED_RETRY_SEC', '300')),
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

    try:
        async with asyncio.TaskGroup() as task_group:
            task_group.create_task(queue.consume(handle_queue_command, settings.worker_concurrency))
            task_group.create_task(schedule_sync_all(queue, settings.sync_interval_sec))
            task_group.create_task(
                schedule_health_check_all(queue, settings.heartbeat_interval_sec)
            )
            task_group.create_task(
                schedule_cleanup_raw_traffic_samples(queue, settings.sync_interval_sec)
            )
            task_group.create_task(schedule_remnawave_reconcile(backend, queue))
            task_group.create_task(recover_stale_operations(backend, queue, settings))
            task_group.create_task(recover_pending_provisions(backend, queue, settings))
    finally:
        close = getattr(queue, 'close', None)
        if close is not None:
            await close()


async def schedule_sync_all(queue: RabbitQueue, interval_sec: float) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        await queue.publish_command(_new_command('sync_all', 'all', None))


async def schedule_cleanup_raw_traffic_samples(queue: RabbitQueue, interval_sec: float) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        await queue.publish_command(_new_command('cleanup_raw_traffic_samples', 'traffic', None))


async def schedule_health_check_all(queue: RabbitQueue, interval_sec: float) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        await queue.publish_command(_new_command('health_check_all', 'all', None))


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
        running_operations = await backend.fetch_stale_operations(
            status='running',
            older_than_seconds=settings.running_timeout_sec,
        )
        for operation in running_operations:
            await backend.timeout_operation(operation['id'])


async def recover_pending_provisions(
    backend: BackendClient,
    queue: RabbitQueue,
    settings: Settings,
) -> None:
    while True:
        await asyncio.sleep(settings.provision_recovery_interval_sec)
        try:
            operations = await backend.create_provision_recovery_operations(
                pending_after_seconds=settings.provision_pending_retry_sec,
                failed_after_seconds=settings.provision_failed_retry_sec,
            )
            for operation in operations:
                await queue.publish_command(command_from_operation(operation))
        except Exception:
            log.exception('Failed to recover pending provisions')
            continue


def _new_command(command: CommandName, target_type: str, target_id: str | None) -> WorkerCommand:
    operation_id = str(uuid4())
    return WorkerCommand.model_validate(
        {
            'command': command,
            'idempotency_key': operation_id,
            'operation_id': operation_id,
            'track_operation': False,
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
