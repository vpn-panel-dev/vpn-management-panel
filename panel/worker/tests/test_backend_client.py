from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest

from app.backend_client import BackendClient


class TransportBackendClient(BackendClient):
    def __init__(self, transport: httpx.AsyncBaseTransport) -> None:
        super().__init__('https://backend.test', 'worker-secret')
        self._transport = transport

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        headers = {'Authorization': 'Bearer worker-secret'}
        async with httpx.AsyncClient(
            base_url='https://backend.test',
            headers=headers,
            transport=self._transport,
        ) as client:
            yield client


@pytest.mark.asyncio
async def test_upsert_remnawave_users_sends_raw_list_body() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'upserted': ['uuid-1'], 'affected_node_ids': []})

    client = TransportBackendClient(httpx.MockTransport(handler))

    users: list[dict[str, Any]] = [
        {'remnawave_uuid': 'uuid-1', 'username': 'alice', 'status': 'ACTIVE'}
    ]
    result = await client.upsert_remnawave_users(users)

    assert result == {'upserted': ['uuid-1'], 'affected_node_ids': []}
    assert json.loads(requests[0].content) == users


@pytest.mark.asyncio
async def test_backend_error_includes_response_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            500,
            json={'detail': 'Remnawave users upsert failed: integer out of range'},
        )

    client = TransportBackendClient(httpx.MockTransport(handler))

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.upsert_remnawave_users(
            [{'remnawave_uuid': 'uuid-1', 'username': 'alice', 'status': 'ACTIVE'}]
        )

    error = str(exc_info.value)
    assert (
        'POST https://backend.test/internal/worker/remnawave/users/upsert failed with 500' in error
    )
    assert 'Remnawave users upsert failed: integer out of range' in error


@pytest.mark.asyncio
async def test_cleanup_raw_traffic_samples_calls_internal_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={'status': 'ok', 'retention_days': 90, 'deleted': 1, 'disabled': False},
        )

    client = TransportBackendClient(httpx.MockTransport(handler))

    result = await client.cleanup_raw_traffic_samples()

    assert result == {'status': 'ok', 'retention_days': 90, 'deleted': 1, 'disabled': False}
    assert requests[0].method == 'POST'
    assert requests[0].url.path == '/internal/worker/traffic/cleanup-raw-samples'


@pytest.mark.asyncio
async def test_heartbeat_and_timeout_internal_endpoints() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'status': 'ok'})

    client = TransportBackendClient(httpx.MockTransport(handler))

    await client.report_heartbeat_result('node-1', {'ok': True})
    await client.timeout_operation('operation-1')

    assert requests[0].method == 'POST'
    assert requests[0].url.path == '/internal/worker/nodes/node-1/heartbeat-result'
    assert json.loads(requests[0].content) == {'ok': True}
    assert requests[1].method == 'POST'
    assert requests[1].url.path == '/internal/worker/operations/operation-1/timeout'
