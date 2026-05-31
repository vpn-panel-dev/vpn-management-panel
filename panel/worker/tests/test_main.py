from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.commands import WorkerCommand
from app.main import Settings, run, schedule_cleanup_raw_traffic_samples


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

    async def fake_sync_all(queue: Any, interval_sec: float) -> None:
        scheduled.append(('sync_all', (queue, interval_sec)))

    async def fake_cleanup(queue: Any, interval_sec: float) -> None:
        scheduled.append(('cleanup', (queue, interval_sec)))

    async def fake_reconcile(backend: Any, queue: Any) -> None:
        scheduled.append(('reconcile', (backend, queue)))

    async def fake_recover(backend: Any, queue: Any, settings: Settings) -> None:
        scheduled.append(('recover', (backend, queue, settings)))

    monkeypatch.setattr('app.main.BackendClient', FakeBackendClient)
    monkeypatch.setattr('app.main.NodeClient', FakeNodeClient)
    monkeypatch.setattr('app.main.CommandHandler', FakeCommandHandler)
    monkeypatch.setattr('app.main.RabbitQueue', FakeQueue)
    monkeypatch.setattr('app.main.schedule_sync_all', fake_sync_all)
    monkeypatch.setattr('app.main.schedule_cleanup_raw_traffic_samples', fake_cleanup)
    monkeypatch.setattr('app.main.schedule_remnawave_reconcile', fake_reconcile)
    monkeypatch.setattr('app.main.recover_stale_operations', fake_recover)

    await run(
        Settings(
            rabbitmq_url='amqp://guest:guest@rabbitmq:5672/',
            backend_internal_url='http://backend.test',
            worker_token='worker-secret',  # noqa: S106
            sync_interval_sec=1,
            worker_concurrency=4,
            recovery_interval_sec=2,
            stale_after_sec=3,
        )
    )

    assert any(call[0] == 'cleanup' and call[1][1] == 1 for call in scheduled)
