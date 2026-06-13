from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

import httpx

from app.backend_client import BackendClient
from app.commands import CommandResult, WorkerCommand
from app.node_client import NodeClient
from app.remnawave_client import (
    PAGE_SIZE,
    RemnawaveClient,
    extract_users_page,
    normalize_user_payload,
)

NodeLockMap = defaultdict[str, asyncio.Lock]
RemnawaveClientFactory = Callable[[str, str], RemnawaveClient | Any]
OperationHandler = Callable[[WorkerCommand], Awaitable[dict[str, Any]]]


class CommandHandler:
    def __init__(
        self,
        backend: BackendClient | Any,
        node_client: NodeClient | Any,
        remnawave_client_factory: RemnawaveClientFactory = RemnawaveClient,
    ) -> None:
        self._backend = backend
        self._node_client = node_client
        self._remnawave_client_factory = remnawave_client_factory
        self._node_locks: NodeLockMap = defaultdict(asyncio.Lock)
        self._operation_handlers: dict[str, OperationHandler] = {
            'sync_all': self._handle_sync_all,
            'sync_node': self._sync_node,
            'provision_node': self._provision_node,
            'health_check_all': self._handle_health_check_all,
            'health_check_node': self._health_check_node,
            'cleanup_raw_traffic_samples': self._cleanup_raw_traffic_samples,
            'remnawave_full_reconcile': self._handle_remnawave_full_reconcile,
            'remnawave_sync_user': self._remnawave_sync_user,
            'remnawave_disable_user': self._remnawave_disable_user,
        }

    async def handle(self, command: WorkerCommand) -> CommandResult:
        try:
            result = await self._dispatch(command)
            if result is None:
                return CommandResult(
                    command=command.command,
                    node_id=command.node_id,
                    ok=True,
                    result={'skipped': True, 'reason': 'operation already handled'},
                )
        except Exception as exc:
            error = str(exc)
            if command.track_operation:
                await self._backend.fail_operation(command.operation_id, error)
            return CommandResult(
                command=command.command,
                node_id=command.node_id,
                ok=False,
                detail=error,
            )

        return CommandResult(
            command=command.command,
            node_id=command.node_id,
            ok=True,
            result=result,
        )

    async def _dispatch(self, command: WorkerCommand) -> dict[str, Any] | None:
        if command.track_operation:
            try:
                await self._backend.start_operation(command.operation_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == HTTPStatus.CONFLICT:
                    return None
                raise

        result = await self._operation_handlers[command.command](command)

        if command.track_operation:
            await self._backend.succeed_operation(command.operation_id, result)
        return result

    async def _handle_sync_all(self, command: WorkerCommand) -> dict[str, Any]:
        _ = command
        return await self._sync_all()

    async def _cleanup_raw_traffic_samples(self, command: WorkerCommand) -> dict[str, Any]:
        _ = command
        return await self._backend.cleanup_raw_traffic_samples()

    async def _handle_health_check_all(self, command: WorkerCommand) -> dict[str, Any]:
        _ = command
        snapshots = await self._backend.fetch_sync_snapshot()
        results = []
        for snapshot in snapshots:
            results.append(await self._heartbeat_snapshot(snapshot))
        reachable = sum(1 for result in results if result.get('ok'))
        return {
            'nodes': len(results),
            'reachable': reachable,
            'unreachable': len(results) - reachable,
        }

    async def _handle_remnawave_full_reconcile(self, command: WorkerCommand) -> dict[str, Any]:
        _ = command
        return await self._remnawave_full_reconcile()

    async def _remnawave_full_reconcile(self) -> dict[str, Any]:
        client = await self._remnawave_client()
        if client is None:
            return {'enabled': False, 'skipped': True}

        start = 0
        fetched = 0
        pages = 0
        upserted = 0
        seen_uuids: set[str] = set()
        while True:
            try:
                payload = await client.list_users(start=start, size=PAGE_SIZE)
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(self._http_error_detail(exc)) from exc
            users, total = extract_users_page(payload)
            if not users:
                break
            seen_uuids.update(
                str(user['remnawave_uuid']) for user in users if user.get('remnawave_uuid')
            )
            result = await self._backend.upsert_remnawave_users(users)
            upserted += self._upserted_count(result, len(users))
            fetched += len(users)
            pages += 1
            start += len(users)
            if total is not None and start >= total:
                break

        completion = await self._backend.complete_remnawave_reconcile(
            {
                'seen_uuids': sorted(seen_uuids),
                'pages': pages,
                'users': fetched,
                'upserted': upserted,
                'total': total,
            }
        )
        return {
            'enabled': True,
            'pages': pages,
            'users': fetched,
            'upserted': upserted,
            'total': total,
            'completion': completion,
        }

    async def _remnawave_sync_user(self, command: WorkerCommand) -> dict[str, Any]:
        user_uuid = self._require_node_id(command)
        client = await self._remnawave_client()
        if client is None:
            return {'enabled': False, 'skipped': True, 'uuid': user_uuid}

        try:
            payload = await client.get_user(user_uuid)
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._http_error_detail(exc)) from exc
        if payload is None:
            raise RuntimeError(f'Remnawave user {user_uuid} was not found')

        user = normalize_user_payload(payload)
        result = await self._backend.upsert_remnawave_users([user])
        return {'uuid': user_uuid, 'deleted': False, **result}

    def _upserted_count(self, result: dict[str, Any], fallback: int) -> int:
        upserted = result.get('upserted')
        if isinstance(upserted, list):
            return len(upserted)
        if upserted is None:
            return fallback
        return int(upserted)

    async def _remnawave_disable_user(self, command: WorkerCommand) -> dict[str, Any]:
        user_uuid = self._require_node_id(command)
        client = await self._remnawave_client()
        if client is None:
            return {'enabled': False, 'skipped': True, 'uuid': user_uuid}

        try:
            result = await client.disable_user(user_uuid)
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._http_error_detail(exc)) from exc
        return {'uuid': user_uuid, 'disabled': True, 'remnawave': result}

    async def _remnawave_client(self) -> RemnawaveClient | Any | None:
        config = await self._backend.fetch_remnawave_config()
        if not config.get('enabled'):
            return None
        base_url = str(config.get('base_url') or '')
        token = str(config.get('api_token') or config.get('token') or '')
        if not base_url or not token:
            raise RuntimeError('Remnawave config is enabled but base_url or api_token is missing')
        return self._remnawave_client_factory(base_url, token)

    def _http_error_detail(self, exc: httpx.HTTPStatusError) -> str:
        response = exc.response
        body = response.text.strip()
        detail = f'Remnawave API request failed with {response.status_code}'
        if body:
            detail = f'{detail}: {body}'
        return detail

    async def _sync_all(self) -> dict[str, Any]:
        snapshots = await self._backend.fetch_sync_snapshot()
        results = []
        for snapshot in snapshots:
            results.append(
                await self._with_node_lock(snapshot['id'], self._sync_snapshot, snapshot)
            )
        succeeded = sum(1 for result in results if result.get('ok'))
        return {'nodes': len(results), 'succeeded': succeeded, 'failed': len(results) - succeeded}

    async def _sync_node(self, command: WorkerCommand) -> dict[str, Any]:
        node_id = self._require_node_id(command)
        snapshot = await self._backend.fetch_node_sync_snapshot(node_id)
        return await self._with_node_lock(node_id, self._sync_snapshot, snapshot)

    async def _provision_node(self, command: WorkerCommand) -> dict[str, Any]:
        node_id = self._require_node_id(command)
        snapshot = await self._backend.fetch_node_provision_snapshot(node_id)
        return await self._with_node_lock(node_id, self._provision_snapshot, snapshot)

    async def _health_check_node(self, command: WorkerCommand) -> dict[str, Any]:
        node_id = self._require_node_id(command)
        snapshot = await self._backend.fetch_node_sync_snapshot(node_id)
        return await self._heartbeat_snapshot(snapshot)

    async def _heartbeat_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        node_id = str(snapshot['id'])
        endpoint = str(snapshot['url']).rstrip('/')
        token = str(snapshot.get('token') or '')
        try:
            await self._node_client.health(endpoint)
            dump = await self._node_client.dump(endpoint, token)
            result = {'ok': True, 'peers': self._peer_results(dump)}
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        await self._backend.report_heartbeat_result(node_id, result)
        return result

    async def _sync_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        node_id = str(snapshot['id'])
        try:
            result = await self._apply_snapshot(snapshot)
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        await self._backend.report_sync_result(node_id, result)
        if not result['ok']:
            raise RuntimeError(str(result['error']))
        return result

    async def _provision_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        node_id = str(snapshot['id'])
        try:
            result = await self._apply_snapshot(snapshot)
        except Exception as exc:
            result = {'ok': False, 'error': str(exc)}
        await self._backend.report_provision_result(node_id, self._provision_result(result))
        if not result['ok']:
            raise RuntimeError(str(result['error']))
        return result

    async def _apply_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        endpoint = str(snapshot['url']).rstrip('/')
        token = str(snapshot.get('token') or '')
        interface = await self._node_client.put_interface(
            endpoint,
            token,
            dict(snapshot['interface']),
        )
        active_peers, peers_to_delete = self._split_peers(snapshot.get('peers', []))
        await self._node_client.put_peers(endpoint, token, active_peers)
        for public_key in peers_to_delete:
            await self._delete_peer_if_present(endpoint, token, public_key)
        status = await self._node_client.status(endpoint, token)
        dump = await self._node_client.dump(endpoint, token)
        return {
            'ok': True,
            'interface': self._interface_result(interface, status, dump),
            'peers': self._peer_results(dump),
        }

    async def _delete_peer_if_present(self, endpoint: str, token: str, public_key: str) -> None:
        try:
            await self._node_client.delete_peer(endpoint, token, public_key)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != HTTPStatus.NOT_FOUND:
                raise

    async def _with_node_lock(
        self,
        node_id: str,
        handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        async with self._node_locks[node_id]:
            return await handler(snapshot)

    def _require_node_id(self, command: WorkerCommand) -> str:
        if not command.target_id:
            raise ValueError(f'{command.command} requires target_id')
        return command.target_id

    def _split_peers(self, peers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        active = []
        delete = []
        for peer in peers:
            public_key = str(peer.get('public_key') or '')
            if not public_key:
                continue
            if peer.get('status') == 'pending_delete' or peer.get('is_blocked'):
                delete.append(public_key)
                continue
            active.append(
                {
                    'public_key': public_key,
                    'allowed_ip': peer.get('allowed_ip'),
                    'psk_key': peer.get('psk_key') or '',
                    'name': peer.get('user_name') or peer.get('user_id') or peer.get('peer_id'),
                }
            )
        return active, delete

    def _interface_result(
        self,
        interface: dict[str, Any],
        status: dict[str, Any],
        dump: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(dump.get('interface') or status.get('interface') or interface)
        if endpoint := status.get('endpoint'):
            result.setdefault('endpoint', endpoint)
        return result

    def _peer_results(self, dump: dict[str, Any]) -> list[dict[str, Any]]:
        peers = dump.get('peers') or []
        results = []
        for peer in peers:
            public_key = peer.get('public_key')
            if not public_key:
                continue
            results.append(
                {
                    'public_key': public_key,
                    'status': peer.get('status') or 'active',
                    'endpoint': peer.get('endpoint'),
                    'rx_bytes': peer.get('rx_bytes'),
                    'tx_bytes': peer.get('tx_bytes'),
                    'last_handshake': peer.get('last_handshake'),
                }
            )
        return results

    def _provision_result(self, result: dict[str, Any]) -> dict[str, Any]:
        if not result.get('ok'):
            return {'ok': False, 'error': result.get('error') or 'provision failed'}
        return {'ok': True, 'interface': result.get('interface')}
