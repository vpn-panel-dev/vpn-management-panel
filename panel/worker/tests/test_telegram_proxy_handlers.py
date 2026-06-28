from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import httpx
from telegram_proxy_contract import (
    EXPECTED_TELEGRAM_PROXY_APPLY_COMMAND_PAYLOAD,
    EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON,
    EXPECTED_TELEGRAM_PROXY_FAILED_RESULT_JSON,
    EXPECTED_TELEGRAM_PROXY_NODE_CONFIG_JSON,
    EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON,
    EXPECTED_TELEGRAM_PROXY_SNAPSHOT_JSON,
    MTPROXY_TEST_KEY,
)

from app.commands import CommandName, WorkerCommand
from app.handlers import CommandHandler


def command(name: CommandName, node_id: str = 'node-1') -> WorkerCommand:
    return WorkerCommand.model_validate(
        {
            'command': name,
            'idempotency_key': f'idem-{name}-{node_id}',
            'operation_id': f'op-{name}-{node_id}',
            'track_operation': True,
            'target_type': 'telegram_proxy_node',
            'target_id': node_id,
            'created_at': datetime.now(UTC).isoformat(),
        }
    )


def snapshot(node_id: str = 'node-1') -> dict[str, Any]:
    return EXPECTED_TELEGRAM_PROXY_SNAPSHOT_JSON | {'node_id': node_id}


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.snapshots = {'node-1': snapshot('node-1')}

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

    async def fetch_telegram_proxy_node_snapshot(self, node_id: str) -> dict[str, Any]:
        self.calls.append(('snapshot', node_id))
        return self.snapshots[node_id]

    async def report_telegram_proxy_node_result(
        self,
        node_id: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append(('telegram_proxy_result', node_id, result))
        return {'status': result['status'], 'ready': result['status'] == 'ready'}


class FakeNode:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.active = 0
        self.max_active = 0

    async def put_mtproxy(
        self,
        endpoint: str,
        token: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        await self._enter_node_call()
        self.calls.append(('put_mtproxy', endpoint, token, config))
        self._exit_node_call()
        return {
            'state': 'running',
            'port': config['port'],
            'public_host': config['public_host'],
            'secret_set': True,
        }

    async def get_mtproxy_status(self, endpoint: str, token: str) -> dict[str, Any]:
        self.calls.append(('get_mtproxy_status', endpoint, token))
        return {
            'state': 'running',
            'port': 443,
            'public_host': 'proxy.example.com',
            'secret_set': True,
        }

    async def delete_mtproxy(self, endpoint: str, token: str) -> dict[str, Any]:
        await self._enter_node_call()
        self.calls.append(('delete_mtproxy', endpoint, token))
        self._exit_node_call()
        return {'state': 'disabled', 'port': None, 'public_host': None, 'secret_set': False}

    async def _enter_node_call(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0)

    def _exit_node_call(self) -> None:
        self.active -= 1


class FailingNode(FakeNode):
    async def put_mtproxy(
        self,
        endpoint: str,
        token: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        _ = (endpoint, token, config)
        raise RuntimeError('node-agent unavailable')


class ReplayBackend(FakeBackend):
    async def start_operation(self, operation_id: str) -> dict[str, Any]:
        _ = operation_id
        request = httpx.Request('POST', 'https://backend.test/internal/worker/operations/op/start')
        response = httpx.Response(HTTPStatus.CONFLICT, request=request, text='already finished')
        raise httpx.HTTPStatusError('conflict', request=request, response=response)


def test_telegram_proxy_apply_command_accepts_exact_backend_payload() -> None:
    parsed = WorkerCommand.model_validate(EXPECTED_TELEGRAM_PROXY_APPLY_COMMAND_PAYLOAD)
    expected = EXPECTED_TELEGRAM_PROXY_APPLY_COMMAND_PAYLOAD

    assert parsed.command == expected['command']
    assert parsed.idempotency_key == expected['idempotency_key']
    assert parsed.operation_id == expected['operation_id']
    assert parsed.track_operation is expected['track_operation']
    assert parsed.target_type == expected['target_type']
    assert parsed.target_id == expected['target_id']
    assert parsed.created_at.isoformat() == expected['created_at']


async def test_apply_node_fetches_snapshot_puts_mtproxy_and_reports_ready() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('telegram_proxy_apply_node'))

    assert result.ok is True
    assert result.result == EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON
    assert node.calls == [
        (
            'put_mtproxy',
            'http://agent.test',
            'node-token',
            EXPECTED_TELEGRAM_PROXY_NODE_CONFIG_JSON,
        )
    ]
    assert backend.calls == [
        ('start', 'op-telegram_proxy_apply_node-node-1'),
        ('snapshot', 'node-1'),
        ('telegram_proxy_result', 'node-1', EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON),
        (
            'succeed',
            'op-telegram_proxy_apply_node-node-1',
            EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON,
        ),
    ]


async def test_check_node_reports_status_without_mutating_node() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('telegram_proxy_check_node'))

    assert result.ok is True
    assert result.result == EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON
    assert node.calls == [('get_mtproxy_status', 'http://agent.test', 'node-token')]
    assert backend.calls == [
        ('start', 'op-telegram_proxy_check_node-node-1'),
        ('snapshot', 'node-1'),
        ('telegram_proxy_result', 'node-1', EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON),
        (
            'succeed',
            'op-telegram_proxy_check_node-node-1',
            EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON,
        ),
    ]


async def test_disable_node_deletes_mtproxy_and_reports_disabled() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('telegram_proxy_disable_node'))

    assert result.ok is True
    assert result.result == EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON
    assert node.calls == [('delete_mtproxy', 'http://agent.test', 'node-token')]
    assert backend.calls == [
        ('start', 'op-telegram_proxy_disable_node-node-1'),
        ('snapshot', 'node-1'),
        ('telegram_proxy_result', 'node-1', EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON),
        (
            'succeed',
            'op-telegram_proxy_disable_node-node-1',
            EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON,
        ),
    ]


async def test_apply_node_failure_reports_backend_failure_before_returning() -> None:
    backend = FakeBackend()
    node = FailingNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('telegram_proxy_apply_node'))

    assert result.ok is False
    assert backend.calls[-2] == (
        'telegram_proxy_result',
        'node-1',
        EXPECTED_TELEGRAM_PROXY_FAILED_RESULT_JSON,
    )
    assert backend.calls[-1][0] == 'fail'
    assert MTPROXY_TEST_KEY not in str(backend.calls[-1])


async def test_apply_and_disable_share_per_node_lock() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    await asyncio.gather(
        handler.handle(command('telegram_proxy_apply_node')),
        handler.handle(command('telegram_proxy_disable_node')),
    )

    assert node.max_active == 1


async def test_malformed_snapshot_fails_without_leaking_secret() -> None:
    backend = FakeBackend()
    backend.snapshots['node-1'] = snapshot('node-1') | {
        'desired': {'enabled': True, 'secret': MTPROXY_TEST_KEY}
    }
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('telegram_proxy_apply_node'))

    assert result.ok is False
    assert backend.calls[-1][0] == 'fail'
    assert MTPROXY_TEST_KEY not in str(backend.calls[-1])


async def test_replayed_telegram_proxy_operation_is_skipped() -> None:
    backend = ReplayBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('telegram_proxy_apply_node'))

    assert result.ok is True
    assert result.result == {'skipped': True, 'reason': 'operation already handled'}
    assert backend.calls == []
    assert node.calls == []
