from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import httpx

from app.commands import CommandName, WorkerCommand
from app.handlers import CommandHandler
from app.main import schedule_remnawave_reconcile

EXPECTED_RECONCILED_USERS = 2
EXPECTED_RECONCILED_PAGES = 2
EXPECTED_RECONCILED_TOTAL = 2
EXPECTED_IDEMPOTENT_UPSERTS = 2
EXPECTED_SCHEDULER_SKIPPED_STATES = 2
EXPECTED_SCHEDULER_COMMANDS = 1


def command(name: CommandName, target_id: str | None = None) -> WorkerCommand:
    return WorkerCommand.model_validate(
        {
            'command': name,
            'idempotency_key': f'idem-{name}-{target_id}',
            'operation_id': f'op-{name}-{target_id}',
            'track_operation': True,
            'target_type': 'remnawave_user' if target_id else 'remnawave',
            'target_id': target_id,
            'created_at': datetime.now(UTC).isoformat(),
        }
    )


def remnawave_user(uuid: str, username: str) -> dict[str, Any]:
    return {'uuid': uuid, 'username': username, 'status': 'ACTIVE'}


class FakeBackend:
    def __init__(self, *, enabled: bool = True, list_upserted: bool = False) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.list_upserted = list_upserted
        self.config = {
            'enabled': enabled,
            'base_url': 'https://remnawave.test',
            'api_token': 'decrypted-token',
        }

    async def start_operation(self, operation_id: str) -> dict[str, Any]:
        self.calls.append(('start', operation_id))
        return {'status': 'running'}

    async def succeed_operation(
        self,
        operation_id: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(('succeed', operation_id, result))

    async def fail_operation(
        self,
        operation_id: str,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(('fail', operation_id, error, result))

    async def fetch_remnawave_config(self) -> dict[str, Any]:
        self.calls.append(('config', None))
        return self.config

    async def upsert_remnawave_users(self, users: list[dict[str, Any]]) -> dict[str, Any]:
        self.calls.append(('upsert', users))
        if self.list_upserted:
            return {'upserted': [user['remnawave_uuid'] for user in users]}
        return {'upserted': len(users)}

    async def mark_remnawave_user_deleted(self, uuid: str) -> dict[str, Any]:
        self.calls.append(('deleted', uuid))
        return {'deleted': True}

    async def complete_remnawave_reconcile(self, result: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(('complete', result))
        return {'status': 'ok', 'affected_node_ids': ['node-1']}


class FakeRemnawaveClient:
    def __init__(self, pages: list[dict[str, Any]], user: dict[str, Any] | None = None) -> None:
        self.pages = pages
        self.user = user
        self.calls: list[tuple[Any, ...]] = []

    async def list_users(self, start: int = 0, size: int = 25) -> dict[str, Any]:
        self.calls.append(('list', start, size))
        return self.pages.pop(0)

    async def get_user(self, uuid: str) -> dict[str, Any] | None:
        self.calls.append(('get', uuid))
        return self.user

    async def disable_user(self, uuid: str) -> dict[str, Any]:
        self.calls.append(('disable', uuid))
        return {'status': 'ok'}


async def test_full_reconcile_paginates_and_upserts_normalized_users() -> None:
    backend = FakeBackend()
    remnawave = FakeRemnawaveClient(
        [
            {'users': [remnawave_user('uuid-1', 'alice')], 'total': 2},
            {'users': [remnawave_user('uuid-2', 'bob')], 'total': 2},
        ]
    )
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_full_reconcile'))

    assert result.ok is True
    assert remnawave.calls == [('list', 0, 25), ('list', 1, 25)]
    complete_call = next(call for call in backend.calls if call[0] == 'complete')
    assert complete_call[1]['seen_uuids'] == ['uuid-1', 'uuid-2']
    assert complete_call[1]['pages'] == EXPECTED_RECONCILED_PAGES
    assert complete_call[1]['users'] == EXPECTED_RECONCILED_USERS
    assert complete_call[1]['upserted'] == EXPECTED_RECONCILED_TOTAL
    assert complete_call[1]['total'] == EXPECTED_RECONCILED_TOTAL
    upserts = [call for call in backend.calls if call[0] == 'upsert']
    assert [call[1][0]['remnawave_uuid'] for call in upserts] == ['uuid-1', 'uuid-2']
    assert backend.calls[-1][0] == 'succeed'
    assert backend.calls[-1][2]['users'] == EXPECTED_RECONCILED_USERS
    assert result.result is not None
    assert result.result['completion'] == {'status': 'ok', 'affected_node_ids': ['node-1']}


async def test_full_reconcile_stops_on_empty_page() -> None:
    backend = FakeBackend()
    remnawave = FakeRemnawaveClient([{'users': [], 'total': 100}])
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_full_reconcile'))

    assert result.ok is True
    assert remnawave.calls == [('list', 0, 25)]
    assert [call for call in backend.calls if call[0] == 'upsert'] == []
    assert (
        'complete',
        {'pages': 0, 'seen_uuids': [], 'total': 100, 'upserted': 0, 'users': 0},
    ) in backend.calls


async def test_full_reconcile_counts_backend_upserted_uuid_list() -> None:
    backend = FakeBackend(list_upserted=True)
    remnawave = FakeRemnawaveClient(
        [
            {
                'users': [remnawave_user('uuid-1', 'alice'), remnawave_user('uuid-2', 'bob')],
                'total': 2,
            }
        ]
    )
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_full_reconcile'))

    assert result.ok is True
    complete_call = next(call for call in backend.calls if call[0] == 'complete')
    assert complete_call[1]['upserted'] == EXPECTED_RECONCILED_TOTAL


async def test_sync_user_upserts_single_user_idempotently() -> None:
    backend = FakeBackend()
    remnawave = FakeRemnawaveClient([], {'user': remnawave_user('uuid-1', 'alice')})
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    await handler.handle(command('remnawave_sync_user', 'uuid-1'))
    await handler.handle(command('remnawave_sync_user', 'uuid-1'))

    upserts = [call for call in backend.calls if call[0] == 'upsert']
    assert len(upserts) == EXPECTED_IDEMPOTENT_UPSERTS
    assert all(call[1][0]['remnawave_uuid'] == 'uuid-1' for call in upserts)


async def test_sync_user_404_fails_without_marking_deleted() -> None:
    backend = FakeBackend()
    remnawave = FakeRemnawaveClient([], None)
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_sync_user', 'uuid-1'))

    assert result.ok is False
    assert result.detail == 'Remnawave user uuid-1 was not found'
    assert ('deleted', 'uuid-1') not in backend.calls
    assert backend.calls[-1] == (
        'fail',
        'op-remnawave_sync_user-uuid-1',
        'Remnawave user uuid-1 was not found',
        None,
    )


async def test_disable_user_calls_remnawave_disable_action() -> None:
    backend = FakeBackend()
    remnawave = FakeRemnawaveClient([])
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_disable_user', 'uuid-1'))

    assert result.ok is True
    assert remnawave.calls == [('disable', 'uuid-1')]
    assert backend.calls[-1][0] == 'succeed'
    assert backend.calls[-1][2]['disabled'] is True


async def test_disabled_config_succeeds_without_remote_calls() -> None:
    backend = FakeBackend(enabled=False)
    remnawave = FakeRemnawaveClient([{'users': [remnawave_user('uuid-1', 'alice')], 'total': 1}])
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_full_reconcile'))

    assert result.ok is True
    assert result.result == {'enabled': False, 'skipped': True}
    assert remnawave.calls == []


async def test_remote_500_fails_operation_with_status_detail() -> None:
    backend = FakeBackend()
    request = httpx.Request('GET', 'https://remnawave.test/api/users')
    response = httpx.Response(500, request=request, text='server exploded')

    class FailingRemnawaveClient(FakeRemnawaveClient):
        async def list_users(self, start: int = 0, size: int = 25) -> dict[str, Any]:
            _ = (start, size)
            raise httpx.HTTPStatusError('boom', request=request, response=response)

    handler = CommandHandler(
        backend,
        object(),
        lambda _base_url, _token: FailingRemnawaveClient([]),
    )

    result = await handler.handle(command('remnawave_full_reconcile'))

    assert result.ok is False
    fail_call = backend.calls[-1]
    assert fail_call[0] == 'fail'
    assert '500' in fail_call[2]
    assert 'server exploded' in fail_call[2]


async def test_malformed_response_fails_operation() -> None:
    backend = FakeBackend()
    remnawave = FakeRemnawaveClient([{'total': 1}])
    handler = CommandHandler(backend, object(), lambda _base_url, _token: remnawave)

    result = await handler.handle(command('remnawave_full_reconcile'))

    assert result.ok is False
    assert backend.calls[-1][0] == 'fail'
    assert 'users list is missing' in backend.calls[-1][2]


async def test_scheduler_does_not_enqueue_when_disabled_or_not_due() -> None:
    backend = PollingBackend([{'enabled': False, 'due': True}, {'enabled': True, 'due': False}])
    queue = FakeQueue()

    task = asyncio.create_task(
        schedule_remnawave_reconcile(cast(Any, backend), cast(Any, queue), interval_sec=0)
    )
    await backend.wait_for_calls(EXPECTED_SCHEDULER_SKIPPED_STATES)
    task.cancel()

    assert queue.commands == []


async def test_scheduler_enqueues_when_enabled_and_due() -> None:
    backend = PollingBackend([{'enabled': True, 'due': True}])
    queue = FakeQueue()

    task = asyncio.create_task(
        schedule_remnawave_reconcile(cast(Any, backend), cast(Any, queue), interval_sec=0)
    )
    await queue.wait_for_commands(EXPECTED_SCHEDULER_COMMANDS)
    task.cancel()

    assert queue.commands[0].command == 'remnawave_full_reconcile'
    assert queue.commands[0].target_type == 'remnawave'


class PollingBackend:
    def __init__(self, states: list[dict[str, Any]]) -> None:
        self.states = states
        self.calls = 0
        self._event = asyncio.Event()

    async def fetch_remnawave_polling_state(self) -> dict[str, Any]:
        self.calls += 1
        self._event.set()
        state = self.states[min(self.calls - 1, len(self.states) - 1)]
        return state

    async def wait_for_calls(self, count: int) -> None:
        while self.calls < count:
            self._event.clear()
            await self._event.wait()


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
