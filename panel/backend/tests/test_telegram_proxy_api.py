from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Node, TelegramProxyNodeState

RAW_SECRET = '0123456789abcdef0123456789abcdef'


@pytest.fixture(autouse=True)
def panel_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')


async def _seed_ready_node(db: AsyncSession) -> Node:
    node = Node(
        id='node-telegram',
        name='telegram-primary',
        url='http://agent:8000',
        token='node-token',  # noqa: S106
        server_endpoint='vpn.example.com:51820',
    )
    state = TelegramProxyNodeState(
        node_id=node.id,
        status='ready',
        public_host='proxy.example.com',
        public_port=443,
    )
    db.add_all([node, state])
    await db.commit()
    return node


async def test_settings_requires_auth(client: AsyncClient):
    # Given: no bearer token is supplied.

    # When: the admin Telegram proxy settings endpoint is requested.
    response = await client.get('/api/telegram-proxy/settings')

    # Then: the shared admin auth dependency rejects the request.
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_update_settings_redacts_secret_and_returns_ready_links(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db: AsyncSession,
):
    # Given: a ready primary node exists.
    node = await _seed_ready_node(db)

    # When: settings are enabled with a raw MTProxy secret.
    response = await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={
            'enabled': True,
            'port': 443,
            'primary_node_id': node.id,
            'secret': RAW_SECRET,
        },
    )

    # Then: the response exposes only secret_set plus generated public links.
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['enabled'] is True
    assert body['port'] == 443
    assert body['primary_node_id'] == node.id
    assert body['secret_set'] is True
    assert 'secret' not in body
    assert 'secret_encrypted' not in body
    assert body['links'] == {
        'tg_url': f'tg://proxy?server=proxy.example.com&port=443&secret={RAW_SECRET}',
        't_me_url': f'https://t.me/proxy?server=proxy.example.com&port=443&secret={RAW_SECRET}',
    }


async def test_update_settings_rejects_invalid_node_port_and_secret(
    client: AsyncClient,
    auth_headers: dict[str, str],
):
    # Given / When / Then: invalid boundary values are rejected before storage.
    missing_node = await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={
            'enabled': True,
            'port': 443,
            'primary_node_id': 'missing-node',
            'secret': RAW_SECRET,
        },
    )
    assert missing_node.status_code == HTTPStatus.NOT_FOUND

    invalid_port = await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={'enabled': True, 'port': 0, 'secret': RAW_SECRET},
    )
    assert invalid_port.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    invalid_secret = await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={'enabled': True, 'port': 443, 'secret': 'not-a-secret'},
    )
    assert invalid_secret.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_status_omits_links_for_stale_primary_state(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db: AsyncSession,
):
    # Given: settings are enabled but the primary state is stale and lacks a public host.
    node = Node(id='stale-node', name='stale', url='http://agent:8000', token='node-token')  # noqa: S106
    state = TelegramProxyNodeState(
        node_id=node.id,
        status='active',
        public_host=None,
        public_port=443,
    )
    db.add_all([node, state])
    await db.commit()
    await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={
            'enabled': True,
            'port': 443,
            'primary_node_id': node.id,
            'secret': RAW_SECRET,
        },
    )

    # When: status is requested.
    response = await client.get('/api/telegram-proxy/status', headers=auth_headers)

    # Then: raw secrets are still redacted and links are not generated from stale state.
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body['settings']['secret_set'] is True
    assert body['primary_node_state']['status'] == 'active'
    assert body['links'] is None
    assert RAW_SECRET not in str(body)


async def test_rotate_secret_redacts_value_and_queues_apply_for_primary(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db: AsyncSession,
):
    # Given: enabled settings with a ready primary node and patched queue publisher.
    node = await _seed_ready_node(db)
    await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={'enabled': True, 'port': 443, 'primary_node_id': node.id, 'secret': RAW_SECRET},
    )

    async def fake_enqueue(node_id: str, **kwargs: str) -> dict[str, str]:
        return {'command': 'telegram_proxy_apply_node', 'target_id': node_id, **kwargs}

    with patch(
        'app.routers.telegram_proxy.enqueue_telegram_proxy_apply_node',
        new=AsyncMock(side_effect=fake_enqueue),
    ) as enqueue:
        # When: the shared secret is rotated.
        response = await client.post('/api/telegram-proxy/rotate-secret', headers=auth_headers)

    # Then: an apply operation is returned and no raw secret is leaked.
    assert response.status_code == HTTPStatus.ACCEPTED
    body = response.json()
    assert body['operation_id']
    assert body['status_url'] == f'/api/operations/{body["operation_id"]}'
    assert RAW_SECRET not in str(body)
    assert 'secret' not in body
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args == (node.id,)


async def test_apply_returns_operation_id_for_primary_node(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db: AsyncSession,
):
    # Given: enabled settings with a ready primary node and patched queue publisher.
    node = await _seed_ready_node(db)
    await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={'enabled': True, 'port': 443, 'primary_node_id': node.id, 'secret': RAW_SECRET},
    )

    with patch(
        'app.routers.telegram_proxy.enqueue_telegram_proxy_apply_node',
        new=AsyncMock(return_value={'command': 'telegram_proxy_apply_node'}),
    ) as enqueue:
        # When: apply is requested.
        response = await client.post('/api/telegram-proxy/apply', headers=auth_headers)

    # Then: the API returns the standard operation handle for polling.
    assert response.status_code == HTTPStatus.ACCEPTED
    body = response.json()
    assert body['operation_id']
    assert body['status_url'] == f'/api/operations/{body["operation_id"]}'
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args == (node.id,)


async def test_disable_returns_operation_id_and_disables_settings(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db: AsyncSession,
):
    # Given: enabled settings with a ready primary node and patched disable publisher.
    node = await _seed_ready_node(db)
    await client.put(
        '/api/telegram-proxy/settings',
        headers=auth_headers,
        json={'enabled': True, 'port': 443, 'primary_node_id': node.id, 'secret': RAW_SECRET},
    )

    with patch(
        'app.routers.telegram_proxy.enqueue_telegram_proxy_disable_node',
        new=AsyncMock(return_value={'command': 'telegram_proxy_disable_node'}),
    ) as enqueue:
        # When: disable is requested.
        response = await client.post('/api/telegram-proxy/disable', headers=auth_headers)

    # Then: a disable operation is queued and subsequent settings show disabled with no links.
    assert response.status_code == HTTPStatus.ACCEPTED
    body = response.json()
    assert body['operation_id']
    assert body['status_url'] == f'/api/operations/{body["operation_id"]}'
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args == (node.id,)

    settings_response = await client.get('/api/telegram-proxy/settings', headers=auth_headers)
    assert settings_response.status_code == HTTPStatus.OK
    settings = settings_response.json()
    assert settings['enabled'] is False
    assert settings['links'] is None
