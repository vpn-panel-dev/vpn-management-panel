import hashlib
import hmac
import json
import logging
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models import Peer, RemnawaveUser, RemnawaveWebhookEvent, User

API_TOKEN = 'fake-remnawave-token'
WEBHOOK_SECRET = 'fake-remnawave-webhook-secret'
FAKE_BASE_URL = 'https://fake-remnawave.test'
REAL_HTTPX_ASYNC_CLIENT = httpx.AsyncClient
log = logging.getLogger(__name__)
pytestmark = pytest.mark.usefixtures('mock_sync_node_enqueue')


def _iso(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


FAKE_USERS = [
    {
        'uuid': 'user-active-uuid',
        'shortUuid': 'active01',
        'username': 'alice',
        'status': 'ACTIVE',
        'expireAt': _iso(30),
        'trafficLimitBytes': 1_000_000_000,
        'trafficUsedBytes': 100_000,
    },
    {
        'uuid': 'user-disabled-uuid',
        'shortUuid': 'disabled01',
        'username': 'bob',
        'status': 'DISABLED',
        'expireAt': _iso(30),
        'trafficLimitBytes': 0,
        'trafficUsedBytes': 0,
    },
    {
        'uuid': 'user-expired-uuid',
        'shortUuid': 'expired01',
        'username': 'charlie',
        'status': 'ACTIVE',
        'expireAt': _iso(-1),
        'trafficLimitBytes': 1_000_000_000,
        'trafficUsedBytes': 500_000,
    },
]


@pytest.fixture()
def fake_remnawave_response() -> dict:
    return {'response': {'users': deepcopy(FAKE_USERS), 'total': len(FAKE_USERS)}}


@pytest.fixture()
def fake_remnawave_transport(fake_remnawave_response) -> httpx.MockTransport:
    users_by_uuid = {
        user['uuid']: deepcopy(user) for user in fake_remnawave_response['response']['users']
    }

    def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers['Authorization'] == f'Bearer {API_TOKEN}'
        if request.url.path == '/api/users':
            return httpx.Response(HTTPStatus.OK, json=fake_remnawave_response)
        if request.url.path.startswith('/api/users/'):
            user_uuid = request.url.path.rsplit('/', 1)[-1]
            user = users_by_uuid.get(user_uuid)
            if user is None:
                return httpx.Response(HTTPStatus.NOT_FOUND, json={'message': 'not found'})
            return httpx.Response(HTTPStatus.OK, json={'response': {'user': user}})
        return httpx.Response(HTTPStatus.NOT_FOUND, json={'message': 'not found'})

    return httpx.MockTransport(_handler)


def _normalize_fake_user(user: dict) -> dict:
    return {
        'uuid': user['uuid'],
        'short_uuid': user.get('shortUuid'),
        'username': user['username'],
        'status': user['status'],
        'expire_at': user.get('expireAt'),
        'traffic_limit_bytes': user.get('trafficLimitBytes', 0),
        'traffic_used_bytes': user.get('trafficUsedBytes', 0),
    }


async def _fetch_fake_users(transport: httpx.MockTransport) -> list[dict]:
    async with httpx.AsyncClient(transport=transport, base_url=FAKE_BASE_URL) as fake_client:
        resp = await fake_client.get(
            '/api/users',
            params={'start': 0, 'size': 25},
            headers={'Authorization': f'Bearer {API_TOKEN}'},
        )
    assert resp.status_code == HTTPStatus.OK
    return resp.json()['response']['users']


def _signed(body: bytes, secret: str = WEBHOOK_SECRET) -> dict[str, str]:
    return {
        'X-Remnawave-Timestamp': str(int(datetime.now(UTC).timestamp())),
        'X-Remnawave-Signature': hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
    }


@pytest.mark.usefixtures('seeded_node')
async def test_full_reconcile_imports_users_and_exposes_ui_state(
    client: AsyncClient,
    auth_headers,
    worker_headers,
    configure_remnawave_settings,
    fake_remnawave_transport: httpx.MockTransport,
):
    headers = auth_headers
    settings = await configure_remnawave_settings(
        client,
        headers,
        base_url=FAKE_BASE_URL,
        api_token=API_TOKEN,
        webhook_secret=WEBHOOK_SECRET,
    )
    serialized = json.dumps(settings)
    assert settings['api_token_set'] is True
    assert settings['webhook_secret_set'] is True
    assert API_TOKEN not in serialized
    assert WEBHOOK_SECRET not in serialized

    with patch('app.routers.remnawave.httpx.AsyncClient') as mock_client_class:
        mock_client_class.side_effect = lambda **kwargs: REAL_HTTPX_ASYNC_CLIENT(
            transport=fake_remnawave_transport,
            **kwargs,
        )
        test_resp = await client.post('/api/remnawave/test', headers=headers)

    fake_users = await _fetch_fake_users(fake_remnawave_transport)
    upsert_resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[_normalize_fake_user(user) for user in fake_users],
        headers=worker_headers,
    )
    users_resp = await client.get('/api/users', headers=headers)

    assert settings['base_url'] == FAKE_BASE_URL
    assert test_resp.status_code == HTTPStatus.OK
    assert test_resp.json() == {'success': True, 'error': None}
    assert upsert_resp.status_code == HTTPStatus.OK
    assert set(upsert_resp.json()['upserted']) == {
        'user-active-uuid',
        'user-disabled-uuid',
        'user-expired-uuid',
    }
    assert users_resp.status_code == HTTPStatus.OK

    users_by_name = {user['name']: user for user in users_resp.json()}
    assert users_by_name['alice']['is_blocked'] is False
    assert users_by_name['bob']['is_blocked'] is True
    assert users_by_name['charlie']['is_blocked'] is True
    assert users_by_name['alice']['remnawave']['status'] == 'ACTIVE'
    assert users_by_name['bob']['remnawave']['status'] == 'DISABLED'
    assert users_by_name['charlie']['remnawave']['traffic_used_bytes'] == 500_000
    assert users_by_name['alice']['peers'] == [
        {
            'node_id': 'node-1',
            'node_name': 'node-1',
            'status': 'pending',
            'last_handshake': None,
            'endpoint': None,
            'online': False,
        }
    ]

    log.info(
        'settings configured: api_token_set=True webhook_secret_set=True secrets_not_returned=True'
    )
    log.info('fake Remnawave full sync imported: ACTIVE=alice DISABLED=bob EXPIRED=charlie')
    log.info('user UI API state: alice active; bob and charlie blocked; Remnawave metadata visible')


async def test_sync_by_uuid_status_change_updates_user(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    initial = _normalize_fake_user(FAKE_USERS[0])
    changed = {**initial, 'status': 'DISABLED'}

    create_resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[initial],
        headers=worker_headers,
    )
    sync_resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[changed],
        headers=worker_headers,
    )

    assert create_resp.status_code == HTTPStatus.OK
    assert sync_resp.status_code == HTTPStatus.OK
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    user = await db.get(User, rw_user.user_id)
    peer = (await db.execute(select(Peer).where(Peer.user_id == user.id))).scalar_one()
    assert rw_user.remnawave_uuid == 'user-active-uuid'
    assert rw_user.status == 'DISABLED'
    assert user.is_blocked is True
    assert peer.status == 'pending_delete'

    log.info('sync-by-uuid status change: user-active-uuid ACTIVE -> DISABLED blocked locally')


@pytest.mark.usefixtures('seeded_node')
async def test_remnawave_sync_overwrites_local_lifecycle_state(
    client: AsyncClient,
    db,
    worker_headers,
):
    initial = _normalize_fake_user(FAKE_USERS[0])

    await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[initial],
        headers=worker_headers,
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    user_id = rw_user.user_id
    user = await db.get(User, rw_user.user_id)
    peer = (await db.execute(select(Peer).where(Peer.user_id == user_id))).scalar_one()

    user.is_blocked = True
    peer.status = 'pending_delete'
    await db.commit()

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[initial],
        headers=worker_headers,
    )

    assert resp.status_code == HTTPStatus.OK
    db.expire_all()
    updated_rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    updated_user = await db.get(User, user_id)
    updated_peer = (await db.execute(select(Peer).where(Peer.user_id == user_id))).scalar_one()
    assert updated_user.is_blocked is False
    assert updated_peer.status == 'pending'
    assert updated_rw_user.sync_status == 'synced'


@pytest.mark.usefixtures('seeded_node')
async def test_webhook_valid_updates_user_and_invalid_is_rejected(
    client: AsyncClient,
    db,
    auth_headers,
    worker_headers,
    configure_remnawave_settings,
):
    headers = auth_headers
    await configure_remnawave_settings(
        client,
        headers,
        base_url=FAKE_BASE_URL,
        api_token=API_TOKEN,
        webhook_secret=WEBHOOK_SECRET,
    )
    await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[_normalize_fake_user(FAKE_USERS[0])],
        headers=worker_headers,
    )

    payload = {
        'event': 'user.updated',
        'timestamp': 'event-valid-1',
        'data': {'uuid': 'user-active-uuid'},
    }
    body = json.dumps(payload).encode()
    with patch('app.routers.api.enqueue_remnawave_sync_user', new=AsyncMock()) as enqueue_sync_user:
        valid_resp = await client.post(
            '/api/remnawave/webhook',
            content=body,
            headers=_signed(body),
        )
        enqueue_sync_user.assert_awaited_once_with('user-active-uuid')

    worker_sync_resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[{**_normalize_fake_user(FAKE_USERS[0]), 'traffic_used_bytes': 777_000}],
        headers=worker_headers,
    )

    invalid_body = json.dumps(
        {
            'event': 'user.updated',
            'timestamp': 'event-invalid-1',
            'data': {'uuid': 'user-active-uuid'},
        }
    ).encode()
    invalid_headers = _signed(invalid_body)
    invalid_headers['X-Remnawave-Signature'] = 'invalid-signature'
    invalid_resp = await client.post(
        '/api/remnawave/webhook',
        content=invalid_body,
        headers=invalid_headers,
    )

    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    event_count = (await db.execute(select(func.count(RemnawaveWebhookEvent.id)))).scalar_one()

    assert valid_resp.status_code == HTTPStatus.OK
    assert valid_resp.json() == {'status': 'queued'}
    assert worker_sync_resp.status_code == HTTPStatus.OK
    assert rw_user.traffic_used_bytes == 777_000
    assert invalid_resp.status_code == HTTPStatus.UNAUTHORIZED
    assert event_count == 1

    log.info('valid webhook accepted: queued sync for user-active-uuid and worker update applied')
    log.info('invalid webhook rejected: HTTP 401 and no extra webhook event recorded')
