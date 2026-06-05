from __future__ import annotations

from typing import Any

import httpx


class NodeClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._timeout = timeout

    async def status(self, endpoint: str, token: str) -> dict[str, Any]:
        response = await self._request('GET', endpoint, token, '/status')
        return dict(response.json())

    async def health(self, endpoint: str) -> dict[str, Any]:
        response = await self._request('GET', endpoint, '', '/health')
        return dict(response.json())

    async def dump(self, endpoint: str, token: str) -> dict[str, Any]:
        response = await self._request('GET', endpoint, token, '/dump')
        return dict(response.json())

    async def put_interface(
        self,
        endpoint: str,
        token: str,
        interface: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request('PUT', endpoint, token, '/interface', json=interface)
        return dict(response.json())

    async def put_peers(
        self,
        endpoint: str,
        token: str,
        peers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        for peer in peers:
            await self._request('PUT', endpoint, token, '/peers', json=peer)
        return {'count': len(peers)}

    async def delete_peer(self, endpoint: str, token: str, public_key: str) -> None:
        await self._request('DELETE', endpoint, token, f'/peers/{public_key}')

    async def _request(
        self,
        method: str,
        endpoint: str,
        token: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            response = await client.request(method, f'{endpoint.rstrip("/")}{path}', **kwargs)
            response.raise_for_status()
            return response
