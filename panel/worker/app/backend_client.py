from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from app.commands import WorkerCommand


class BackendClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip('/')
        self._token = token
        self._timeout = timeout

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        headers = {'Authorization': f'Bearer {self._token}'}
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        ) as client:
            yield client

    async def start_operation(self, operation_id: str) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.post(f'/internal/worker/operations/{operation_id}/start')
            response.raise_for_status()
            return response.json()

    async def succeed_operation(
        self,
        operation_id: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        async with self._client() as client:
            response = await client.post(
                f'/internal/worker/operations/{operation_id}/succeed',
                json={'result': result},
            )
            response.raise_for_status()

    async def fail_operation(
        self,
        operation_id: str,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        async with self._client() as client:
            response = await client.post(
                f'/internal/worker/operations/{operation_id}/fail',
                json={'error': error, 'result': result},
            )
            response.raise_for_status()

    async def fetch_sync_snapshot(self) -> list[dict[str, Any]]:
        async with self._client() as client:
            response = await client.get('/internal/worker/sync/snapshot')
            response.raise_for_status()
            return list(response.json().get('nodes', []))

    async def fetch_node_sync_snapshot(self, node_id: str) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.get(f'/internal/worker/nodes/{node_id}/sync-snapshot')
            response.raise_for_status()
            return dict(response.json())

    async def fetch_node_provision_snapshot(self, node_id: str) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.get(f'/internal/worker/nodes/{node_id}/provision-snapshot')
            response.raise_for_status()
            return dict(response.json())

    async def report_sync_result(self, node_id: str, result: dict[str, Any]) -> None:
        async with self._client() as client:
            response = await client.post(
                f'/internal/worker/nodes/{node_id}/sync-result',
                json=result,
            )
            response.raise_for_status()

    async def report_provision_result(self, node_id: str, result: dict[str, Any]) -> None:
        async with self._client() as client:
            response = await client.post(
                f'/internal/worker/nodes/{node_id}/provision-result',
                json=result,
            )
            response.raise_for_status()

    async def report_heartbeat_result(self, node_id: str, result: dict[str, Any]) -> None:
        async with self._client() as client:
            response = await client.post(
                f'/internal/worker/nodes/{node_id}/heartbeat-result',
                json=result,
            )
            response.raise_for_status()

    async def timeout_operation(self, operation_id: str) -> None:
        async with self._client() as client:
            response = await client.post(f'/internal/worker/operations/{operation_id}/timeout')
            response.raise_for_status()

    async def fetch_stale_operations(
        self,
        status: str = 'queued',
        older_than_seconds: int = 30,
    ) -> list[dict[str, Any]]:
        async with self._client() as client:
            response = await client.get(
                '/internal/worker/operations/stale',
                params={'status': status, 'older_than_seconds': older_than_seconds},
            )
            response.raise_for_status()
            return list(response.json().get('operations', []))

    async def fetch_remnawave_config(self) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.get('/internal/worker/remnawave/config')
            response.raise_for_status()
            return dict(response.json())

    async def cleanup_raw_traffic_samples(self) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.post('/internal/worker/traffic/cleanup-raw-samples')
            response.raise_for_status()
            return dict(response.json())

    async def fetch_remnawave_polling_state(self) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.get('/internal/worker/remnawave/polling-state')
            response.raise_for_status()
            return dict(response.json())

    async def upsert_remnawave_users(self, users: list[dict[str, Any]]) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.post(
                '/internal/worker/remnawave/users/upsert',
                json=users,
            )
            response.raise_for_status()
            return dict(response.json())

    async def mark_remnawave_user_deleted(self, uuid: str) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.post(f'/internal/worker/remnawave/users/{uuid}/deleted')
            response.raise_for_status()
            return dict(response.json())

    async def complete_remnawave_reconcile(self, result: dict[str, Any]) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.post(
                '/internal/worker/remnawave/reconcile-complete',
                json=result,
            )
            response.raise_for_status()
            return dict(response.json())


def command_from_operation(operation: dict[str, Any]) -> WorkerCommand:
    return WorkerCommand.model_validate(
        {
            'command': operation['kind'],
            'idempotency_key': operation['id'],
            'operation_id': operation['id'],
            'target_type': operation.get('target_type') or 'all',
            'target_id': operation.get('target_id'),
            'created_at': operation['updated_at'],
        }
    )
