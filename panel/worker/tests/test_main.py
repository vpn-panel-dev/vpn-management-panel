from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.commands import WorkerCommand
from app.main import (
    Settings,
    recover_pending_provisions,
    recover_stale_operations,
    run,
    schedule_cleanup_raw_traffic_samples,
    schedule_health_check_all,
)

HEARTBEAT_INTERVAL_SEC = 5


class FakeQueue:
    def __init__(self) -> None:
        self.commands: list[WorkerCommand] = []
        self._event = asyncio.Event()

    async def publish_command(self, command: WorkerCommand) -> None:
        self.commands.append(command)
        self._event.set()

    async def wait_for_commands(self, count: int) -> None:
        while len(self.commands) < count:
            self._event.clear()
            await self._event.wait()


@pytest.mark.asyncio
async def test_cleanup_scheduler_enqueues_raw_traffic_cleanup() -> None:
    queue = FakeQueue()

    task = asyncio.create_task(schedule_cleanup_raw_traffic_samples(queue, interval_sec=0))
    await queue.wait_for_commands(1)
    task.cancel()

    assert queue.commands[0].command == 'cleanup_raw_traffic_samples'
    assert queue.commands[0].target_type == 'traffic'
    assert queue.commands[0].target_id is None


@pytest.mark.asyncio
async def test_heartbeat_scheduler_enqueues_health_check() -> None:
    queue = FakeQueue()

    task = asyncio.create_task(schedule_health_check_all(queue, interval_sec=0))
    await queue.wait_for_commands(1)
    task.cancel()

    assert queue.commands[0].command == 'health_check_all'
    assert queue.commands[0].target_type == 'all'
    assert queue.commands[0].target_id is None


@pytest.mark.asyncio
async def test_recovery_republishes_queued_and_times_out_running() -> None:
    class FakeBackend:
        def __init__(self) -> None:
            self.fetches: list[tuple[str, int]] = []
            self.timed_out: list[str] = []

        async def fetch_stale_operations(self, status: str, older_than_seconds: int):
            self.fetches.append((status, older_than_seconds))
            if status == 'queued':
                return [
                    {
                        'id': 'queued-op',
                        'kind': 'sync_all',
                        'target_type': 'all',
                        'target_id': None,
                        'updated_at': '2026-06-05T00:00:00+00:00',
                    }
                ]
            return [{'id': 'running-op'}]

        async def timeout_operation(self, operation_id: str) -> None:
            self.timed_out.append(operation_id)

    backend = FakeBackend()
    queue = FakeQueue()
    settings = Settings(
        rabbitmq_url='amqp://guest:guest@rabbitmq:5672/',
        backend_internal_url='http://backend.test',
        worker_token='worker-secret',  # noqa: S106
        recovery_interval_sec=0,
        stale_after_sec=30,
        running_timeout_sec=300,
    )

    task = asyncio.create_task(recover_stale_operations(backend, queue, settings))
    await queue.wait_for_commands(1)
    task.cancel()

    assert queue.commands[0].operation_id == 'queued-op'
    assert backend.fetches == [('queued', 30), ('running', 300)]
    assert backend.timed_out == ['running-op']


@pytest.mark.asyncio
async def test_provision_recovery_creates_and_publishes_retry_operations() -> None:
    class FakeBackend:
        def __init__(self) -> None:
            self.calls: list[tuple[int, int]] = []

        async def create_provision_recovery_operations(
            self,
            *,
            pending_after_seconds: int,
            failed_after_seconds: int,
        ):
            self.calls.append((pending_after_seconds, failed_after_seconds))
            return [
                {
                    'id': 'provision-op',
                    'kind': 'provision_node',
                    'target_type': 'node',
                    'target_id': 'node-1',
                    'updated_at': '2026-06-05T00:00:00+00:00',
                }
            ]

    backend = FakeBackend()
    queue = FakeQueue()
    settings = Settings(
        rabbitmq_url='amqp://guest:guest@rabbitmq:5672/',
        backend_internal_url='http://backend.test',
        worker_token='worker-secret',  # noqa: S106
        provision_recovery_interval_sec=0,
        provision_pending_retry_sec=60,
        provision_failed_retry_sec=300,
    )

    task = asyncio.create_task(recover_pending_provisions(backend, queue, settings))
    await queue.wait_for_commands(1)
    task.cancel()

    assert backend.calls == [(60, 300)]
    assert queue.commands[0].command == 'provision_node'
    assert queue.commands[0].operation_id == 'provision-op'
    assert queue.commands[0].target_id == 'node-1'


@pytest.mark.asyncio
async def test_run_schedules_cleanup_job_in_steady_state_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scheduled: list[tuple[str, tuple[Any, ...]]] = []

    class FakeBackendClient:
        def __init__(self, base_url: str, token: str) -> None:
            scheduled.append(('backend', (base_url, token)))

    class FakeNodeClient:
        def __init__(self) -> None:
            scheduled.append(('node_client', ()))

    class FakeCommandHandler:
        def __init__(self, backend: Any, node_client: Any) -> None:
            scheduled.append(('handler', (backend, node_client)))

    class FakeQueue:
        def __init__(self, url: str) -> None:
            self.url = url
            scheduled.append(('queue', (url,)))

        async def consume(self, handler: Any, concurrency: int) -> None:
            scheduled.append(('consume', (handler, concurrency)))

        async def close(self) -> None:
            scheduled.append(('close', ()))

    async def fake_sync_all(queue: Any, interval_sec: float) -> None:
        scheduled.append(('sync_all', (queue, interval_sec)))

    async def fake_cleanup(queue: Any, interval_sec: float) -> None:
        scheduled.append(('cleanup', (queue, interval_sec)))

    async def fake_heartbeat(queue: Any, interval_sec: float) -> None:
        scheduled.append(('heartbeat', (queue, interval_sec)))

    async def fake_reconcile(backend: Any, queue: Any) -> None:
        scheduled.append(('reconcile', (backend, queue)))

    async def fake_recover(backend: Any, queue: Any, settings: Settings) -> None:
        scheduled.append(('recover', (backend, queue, settings)))

    async def fake_recover_provisions(backend: Any, queue: Any, settings: Settings) -> None:
        scheduled.append(('recover_provisions', (backend, queue, settings)))

    monkeypatch.setattr('app.main.BackendClient', FakeBackendClient)
    monkeypatch.setattr('app.main.NodeClient', FakeNodeClient)
    monkeypatch.setattr('app.main.CommandHandler', FakeCommandHandler)
    monkeypatch.setattr('app.main.RabbitQueue', FakeQueue)
    monkeypatch.setattr('app.main.schedule_sync_all', fake_sync_all)
    monkeypatch.setattr('app.main.schedule_health_check_all', fake_heartbeat)
    monkeypatch.setattr('app.main.schedule_cleanup_raw_traffic_samples', fake_cleanup)
    monkeypatch.setattr('app.main.schedule_remnawave_reconcile', fake_reconcile)
    monkeypatch.setattr('app.main.recover_stale_operations', fake_recover)
    monkeypatch.setattr('app.main.recover_pending_provisions', fake_recover_provisions)

    await run(
        Settings(
            rabbitmq_url='amqp://guest:guest@rabbitmq:5672/',
            backend_internal_url='http://backend.test',
            worker_token='worker-secret',  # noqa: S106
            sync_interval_sec=1,
            worker_concurrency=4,
            heartbeat_interval_sec=HEARTBEAT_INTERVAL_SEC,
            recovery_interval_sec=2,
            stale_after_sec=3,
        )
    )

    assert any(call[0] == 'cleanup' and call[1][1] == 1 for call in scheduled)
    assert any(
        call[0] == 'heartbeat' and call[1][1] == HEARTBEAT_INTERVAL_SEC for call in scheduled
    )
    assert any(call[0] == 'recover_provisions' for call in scheduled)
