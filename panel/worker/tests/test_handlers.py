from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import httpx

from app.commands import CommandName, WorkerCommand
from app.handlers import CommandHandler


def command(name: CommandName, node_id: str | None = 'node-1') -> WorkerCommand:
    target_type = 'traffic' if name == 'cleanup_raw_traffic_samples' else 'all'
    return WorkerCommand.model_validate(
        {
            'command': name,
            'idempotency_key': f'idem-{name}',
            'operation_id': f'op-{name}',
            'target_type': target_type if node_id is None else 'node',
            'target_id': node_id,
            'created_at': datetime.now(UTC).isoformat(),
        }
    )


def snapshot(node_id: str = 'node-1') -> dict[str, Any]:
    return {
        'id': node_id,
        'name': 'Node 1',
        'url': 'http://agent.test',
        'token': 'node-token',
        'provision_status': 'pending',
        'interface': {'private_key': 'server-private', 'listen_port': 51820, 'mtu': '1376'},
        'peers': [
            {
                'peer_id': 'peer-1',
                'user_id': 'user-1',
                'user_name': 'Alice',
                'public_key': 'pub-1',
                'allowed_ip': '10.8.0.2',
                'psk_key': 'psk-1',
                'status': 'pending',
                'is_blocked': False,
            },
            {
                'peer_id': 'peer-2',
                'user_id': 'user-2',
                'user_name': 'Bob',
                'public_key': 'pub-2',
                'allowed_ip': '10.8.0.3',
                'psk_key': 'psk-2',
                'status': 'pending_delete',
                'is_blocked': False,
            },
        ],
    }


class FakeBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.snapshots = {'node-1': snapshot('node-1')}

    async def start_operation(self, operation_id: str) -> dict[str, Any]:
        self.calls.append(('start', operation_id))
        return {'status': 'running', 'attempts': 1}

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

    async def fetch_sync_snapshot(self) -> list[dict[str, Any]]:
        self.calls.append(('fetch_sync_snapshot', None))
        return list(self.snapshots.values())

    async def fetch_node_sync_snapshot(self, node_id: str) -> dict[str, Any]:
        self.calls.append(('fetch_node_sync_snapshot', node_id))
        return self.snapshots[node_id]

    async def fetch_node_provision_snapshot(self, node_id: str) -> dict[str, Any]:
        self.calls.append(('fetch_node_provision_snapshot', node_id))
        return self.snapshots[node_id]

    async def report_sync_result(self, node_id: str, result: dict[str, Any]) -> None:
        self.calls.append(('sync_result', node_id, result))

    async def report_provision_result(self, node_id: str, result: dict[str, Any]) -> None:
        self.calls.append(('provision_result', node_id, result))

    async def report_heartbeat_result(self, node_id: str, result: dict[str, Any]) -> None:
        self.calls.append(('heartbeat_result', node_id, result))

    async def cleanup_raw_traffic_samples(self) -> dict[str, Any]:
        self.calls.append(('cleanup_raw_traffic_samples', None))
        return {'status': 'ok', 'retention_days': 90, 'deleted': 2, 'disabled': False}


class FakeNode:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.active = 0
        self.max_active = 0

    async def put_interface(
        self,
        endpoint: str,
        token: str,
        interface: dict[str, Any],
    ) -> dict[str, Any]:
        await self._enter_node_call()
        self.calls.append(('put_interface', endpoint, token, interface))
        self._exit_node_call()
        return {
            'public_key': 'server-public',
            'listen_port': interface['listen_port'],
            'mtu': '1376',
        }

    async def put_peers(
        self,
        endpoint: str,
        token: str,
        peers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        await self._enter_node_call()
        self.calls.append(('put_peers', endpoint, token, peers))
        self._exit_node_call()
        return {'count': len(peers)}

    async def delete_peer(self, endpoint: str, token: str, public_key: str) -> None:
        self.calls.append(('delete_peer', endpoint, token, public_key))

    async def status(self, endpoint: str, token: str) -> dict[str, Any]:
        self.calls.append(('status', endpoint, token))
        return {'endpoint': 'vpn.test:51820'}

    async def dump(self, endpoint: str, token: str) -> dict[str, Any]:
        self.calls.append(('dump', endpoint, token))
        return {
            'interface': {'public_key': 'server-public', 'listen_port': 51820, 'mtu': '1376'},
            'peers': [
                {
                    'public_key': 'pub-1',
                    'status': 'active',
                    'endpoint': '203.0.113.10:54321',
                    'rx_bytes': 10,
                    'tx_bytes': 20,
                }
            ],
        }

    async def health(self, endpoint: str) -> dict[str, Any]:
        self.calls.append(('health', endpoint))
        return {'status': 'ok'}

    async def _enter_node_call(self) -> None:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0)

    def _exit_node_call(self) -> None:
        self.active -= 1


class FailingNode(FakeNode):
    async def put_interface(
        self,
        endpoint: str,
        token: str,
        interface: dict[str, Any],
    ) -> dict[str, Any]:
        _ = (endpoint, token, interface)
        raise RuntimeError('node-agent unavailable')


class ReplayBackend(FakeBackend):
    async def start_operation(self, operation_id: str) -> dict[str, Any]:
        _ = operation_id
        request = httpx.Request('POST', 'https://backend.test/internal/worker/operations/op/start')
        response = httpx.Response(HTTPStatus.CONFLICT, request=request, text='already finished')
        raise httpx.HTTPStatusError('conflict', request=request, response=response)


async def test_sync_node_applies_snapshot_and_reports_success() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('sync_node'))

    assert result.ok is True
    assert ('start', 'op-sync_node') in backend.calls
    assert backend.calls[-1][0] == 'succeed'
    assert any(call[0] == 'sync_result' for call in backend.calls)
    sync_reports = [call for call in backend.calls if call[0] == 'sync_result']
    assert sync_reports[0][2]['peers'][0]['endpoint'] == '203.0.113.10:54321'
    assert any(call[0] == 'put_interface' for call in node.calls)
    assert ('delete_peer', 'http://agent.test', 'node-token', 'pub-2') in node.calls


async def test_provision_node_reports_provision_result() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('provision_node'))

    provision_reports = [call for call in backend.calls if call[0] == 'provision_result']

    assert result.ok is True
    assert provision_reports == [
        (
            'provision_result',
            'node-1',
            {
                'ok': True,
                'interface': {
                    'public_key': 'server-public',
                    'listen_port': 51820,
                    'mtu': '1376',
                    'endpoint': 'vpn.test:51820',
                },
            },
        )
    ]


async def test_cleanup_raw_traffic_samples_calls_backend_cleanup() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('cleanup_raw_traffic_samples', None))

    assert result.ok is True
    assert result.result == {'status': 'ok', 'retention_days': 90, 'deleted': 2, 'disabled': False}
    assert ('cleanup_raw_traffic_samples', None) in backend.calls
    assert backend.calls[-1] == (
        'succeed',
        'op-cleanup_raw_traffic_samples',
        {'status': 'ok', 'retention_days': 90, 'deleted': 2, 'disabled': False},
    )


async def test_health_check_all_reports_reachability() -> None:
    backend = FakeBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('health_check_all', None))

    assert result.ok is True
    assert result.result == {'nodes': 1, 'reachable': 1, 'unreachable': 0}
    assert ('health', 'http://agent.test') in node.calls
    assert ('heartbeat_result', 'node-1', {'ok': True}) in backend.calls


async def test_sync_all_uses_per_node_lock() -> None:
    backend = FakeBackend()
    backend.snapshots = {
        'node-1': snapshot('node-1'),
        'node-2': snapshot('node-1') | {'id': 'node-1'},
    }
    node = FakeNode()
    handler = CommandHandler(backend, node)

    await asyncio.gather(
        handler.handle(command('sync_all', None)),
        handler.handle(command('sync_node')),
    )

    assert node.max_active == 1


async def test_failure_is_reported_before_handler_returns() -> None:
    backend = FakeBackend()
    node = FailingNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('sync_node'))

    assert result.ok is False
    assert backend.calls[-1][0] == 'fail'


async def test_replayed_operation_is_skipped_without_failing_backend() -> None:
    backend = ReplayBackend()
    node = FakeNode()
    handler = CommandHandler(backend, node)

    result = await handler.handle(command('sync_node'))

    assert result.ok is True
    assert result.result == {'skipped': True, 'reason': 'operation already handled'}
    assert backend.calls == []
