from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

PAGE_SIZE = 25


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._token = token
        self._timeout = timeout
        self._transport = transport

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        headers = {'Authorization': f'Bearer {self._token}'}
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            yield client

    async def list_users(self, start: int = 0, size: int = PAGE_SIZE) -> dict[str, Any]:
        async with self._client() as client:
            response = await client.get('/api/users', params={'start': start, 'size': size})
            response.raise_for_status()
            return dict(response.json())

    async def get_user(self, uuid: str) -> dict[str, Any] | None:
        async with self._client() as client:
            response = await client.get(f'/api/users/{uuid}')
            if response.status_code == httpx.codes.NOT_FOUND:
                return None
            response.raise_for_status()
            return dict(response.json())


def extract_users_page(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    data = _unwrap_payload(payload)
    users = _value(data, 'users', 'items', 'data')
    if not isinstance(users, list):
        raise TypeError('Malformed Remnawave users response: users list is missing')

    total = data.get('total') or data.get('totalCount') or data.get('count')
    if total is not None and not isinstance(total, int):
        raise ValueError('Malformed Remnawave users response: total must be an integer')

    normalized_users = []
    for user in users:
        if not isinstance(user, dict):
            raise TypeError('Malformed Remnawave users response: user must be an object')
        normalized_users.append(normalize_user(user))
    return normalized_users, total


def normalize_user_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = _unwrap_payload(payload)
    if 'user' in data:
        user = data['user']
        if not isinstance(user, dict):
            raise ValueError('Malformed Remnawave user response: user must be an object')
        return normalize_user(user)
    return normalize_user(data)


def normalize_user(user: dict[str, Any]) -> dict[str, Any]:
    remnawave_uuid = _value(user, 'uuid', 'remnawave_uuid')
    if not remnawave_uuid:
        raise ValueError('Malformed Remnawave user response: uuid is missing')

    return {
        'remnawave_uuid': str(remnawave_uuid),
        'remnawave_id': _value(user, 'id', 'remnawave_id'),
        'short_uuid': _value(user, 'shortUuid', 'short_uuid'),
        'username': str(_value(user, 'username', default='')),
        'status': str(_value(user, 'status', default='UNKNOWN')),
        'expire_at': _value(user, 'expireAt', 'expire_at'),
        'email': _value(user, 'email'),
        'tag': _value(user, 'tag'),
        'telegram_id': _value(user, 'telegramId', 'telegram_id'),
        'description': _value(user, 'description'),
        'traffic_limit_bytes': _value(user, 'trafficLimitBytes', 'traffic_limit_bytes', default=0),
        'traffic_limit_strategy': _value(
            user,
            'trafficLimitStrategy',
            'traffic_limit_strategy',
            default='NO_RESET',
        ),
        'traffic_used_bytes': _value(user, 'trafficUsedBytes', 'traffic_used_bytes', default=0),
        'lifetime_used_traffic_bytes': _value(
            user,
            'lifetimeUsedTrafficBytes',
            'lifetime_used_traffic_bytes',
            default=0,
        ),
        'last_traffic_reset_at': _value(user, 'lastTrafficResetAt', 'last_traffic_reset_at'),
        'online_at': _value(user, 'onlineAt', 'online_at'),
        'first_connected_at': _value(user, 'firstConnectedAt', 'first_connected_at'),
        'last_connected_node_uuid': _value(
            user,
            'lastConnectedNodeUuid',
            'last_connected_node_uuid',
        ),
        'hwid_device_limit': _value(user, 'hwidDeviceLimit', 'hwid_device_limit'),
        'external_squad_uuid': _value(user, 'externalSquadUuid', 'external_squad_uuid'),
        'active_internal_squads': _value(user, 'activeInternalSquads', 'active_internal_squads'),
        'subscription_url': _value(user, 'subscriptionUrl', 'subscription_url'),
        'created_at': _value(user, 'createdAt', 'created_at'),
        'updated_at': _value(user, 'updatedAt', 'updated_at'),
    }


def _unwrap_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get('response') or payload.get('data') or payload
    if not isinstance(data, dict):
        raise TypeError('Malformed Remnawave response: payload must be an object')
    return data


def _value(user: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in user:
            return user[name]
    return default
