from datetime import timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    LocalAmneziawgUserLifetimeTraffic,
    Node,
    TelegramProxyNodeState,
    TelegramProxySettings,
    User,
)
from app.mtproxy_secret_crypto import encrypt
from app.services.local_lifecycle import now

PROXY_SECRET = '0123456789abcdef0123456789abcdef'
EXPECTED_PROXY = {
    'enabled': True,
    'primary_node_name': 'primary proxy',
    'tg_url': (
        'tg://proxy?server=proxy.example.com&port=443&secret='
        'ee0123456789abcdef0123456789abcdef636c6f756473796e6370726f2e6e6574'
    ),
    'https_url': (
        'https://t.me/proxy?server=proxy.example.com&port=443&secret='
        'ee0123456789abcdef0123456789abcdef636c6f756473796e6370726f2e6e6574'
    ),
    'status': 'ready',
}


async def _seed_ready_proxy(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: public proxy settings point at a ready primary node with private agent credentials.
    monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
    primary = Node(
        id='primary-proxy-node',
        name='primary proxy',
        url='http://private-primary-agent:8000',
        token='private-primary-token',  # noqa: S106
    )
    fallback = Node(
        id='fallback-proxy-node',
        name='fallback proxy',
        url='http://private-fallback-agent:8000',
        token='private-fallback-token',  # noqa: S106
    )
    db.add_all(
        [
            primary,
            fallback,
            TelegramProxySettings(
                enabled=True,
                port=443,
                secret_encrypted=encrypt(PROXY_SECRET),
                primary_node_id=primary.id,
            ),
            TelegramProxyNodeState(
                node_id=primary.id,
                status='ready',
                public_host='proxy.example.com',
                public_port=443,
            ),
            TelegramProxyNodeState(
                node_id=fallback.id,
                status='ready',
                public_host='fallback.example.com',
                public_port=443,
            ),
        ]
    )
    await db.commit()


async def test_pub_user_info_includes_proxy_for_active_token(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an active local user and ready Telegram proxy settings.
    await _seed_ready_proxy(db, monkeypatch)
    user = User(name='active-public-user')
    db.add(user)
    await db.commit()

    # When: the public info endpoint is requested by valid public token.
    response = await client.get(f'/pub/u/{user.public_token}/info')

    # Then: the response includes only the safe primary proxy payload.
    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload['telegram_proxy'] == EXPECTED_PROXY
    assert 'fallback.example.com' not in str(payload)
    assert 'private-primary-agent' not in str(payload)
    assert 'private-primary-token' not in str(payload)


async def test_pub_user_info_includes_proxy_for_blocked_token_with_empty_nodes(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a blocked local user and ready Telegram proxy settings.
    await _seed_ready_proxy(db, monkeypatch)
    user = User(name='blocked-public-user', is_blocked=True)
    db.add(user)
    await db.commit()

    # When: the public info endpoint is requested by valid public token.
    response = await client.get(f'/pub/u/{user.public_token}/info')

    # Then: VPN configs remain hidden while Telegram proxy remains visible.
    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload['blocked'] is True
    assert payload['nodes'] == []
    assert payload['telegram_proxy'] == EXPECTED_PROXY


async def test_pub_user_info_includes_proxy_for_expired_and_limited_tokens(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: expired and limited users still have valid public tokens.
    await _seed_ready_proxy(db, monkeypatch)
    expired = User(name='expired-public-user', expire_at=now() - timedelta(days=1))
    limited = User(name='limited-public-user', traffic_limit_bytes=10)
    db.add_all([expired, limited])
    await db.flush()
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=limited.id,
            rx_bytes=5,
            tx_bytes=5,
            total_bytes=10,
            updated_at=now(),
        )
    )
    await db.commit()

    # When: both valid public-token dashboards are requested.
    expired_response = await client.get(f'/pub/u/{expired.public_token}/info')
    limited_response = await client.get(f'/pub/u/{limited.public_token}/info')

    # Then: lifecycle status does not suppress the Telegram proxy payload.
    assert expired_response.status_code == HTTPStatus.OK
    assert limited_response.status_code == HTTPStatus.OK
    assert expired_response.json()['telegram_proxy'] == EXPECTED_PROXY
    assert limited_response.json()['telegram_proxy'] == EXPECTED_PROXY


async def test_pub_user_info_returns_null_proxy_when_settings_disabled_or_not_ready(
    client: AsyncClient, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: disabled settings and a primary node whose state is stale.
    monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
    primary = Node(
        id='stale-proxy-node',
        name='stale proxy',
        url='http://private-stale-agent:8000',
        token='private-stale-token',  # noqa: S106
    )
    user = User(name='disabled-proxy-user')
    settings = TelegramProxySettings(
        enabled=False,
        port=443,
        secret_encrypted=encrypt(PROXY_SECRET),
        primary_node_id=primary.id,
    )
    state = TelegramProxyNodeState(
        node_id=primary.id,
        status='error',
        public_host='stale.example.com',
        public_port=443,
    )
    db.add_all(
        [
            primary,
            user,
            settings,
            state,
        ]
    )
    await db.commit()

    # When: the public info endpoint is requested.
    response = await client.get(f'/pub/u/{user.public_token}/info')

    # Then: dashboard fields still render and proxy is explicitly null.
    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload['blocked'] is False
    assert payload['status'] == {'code': 'active', 'reason': None}
    assert payload['telegram_proxy'] is None
    assert 'private-stale-agent' not in str(payload)
    assert 'private-stale-token' not in str(payload)

    # When: settings are enabled but primary state is stale and cannot produce public links.
    settings.enabled = True
    state.status = 'active'
    state.public_host = None
    await db.commit()
    stale_response = await client.get(f'/pub/u/{user.public_token}/info')

    # Then: not-ready proxy state remains null without affecting dashboard fields.
    assert stale_response.status_code == HTTPStatus.OK
    stale_payload = stale_response.json()
    assert stale_payload['blocked'] is False
    assert stale_payload['status'] == {'code': 'active', 'reason': None}
    assert stale_payload['telegram_proxy'] is None
    assert 'private-stale-agent' not in str(stale_payload)
    assert 'private-stale-token' not in str(stale_payload)


async def test_pub_user_info_invalid_token_remains_not_found(client: AsyncClient) -> None:
    # Given / When: a public token does not match any user.
    response = await client.get('/pub/u/not-a-valid-token/info')

    # Then: the endpoint remains a 404 and does not reveal proxy availability.
    assert response.status_code == HTTPStatus.NOT_FOUND
