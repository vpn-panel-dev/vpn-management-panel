from http import HTTPStatus

import pytest
from httpx import AsyncClient

from app.models import Node, TelegramProxyNodeState, TelegramProxySettings
from app.mtproxy_secret_crypto import encrypt
from app.services.telegram_proxy import select_primary_node_state

EXPECTED_TELEGRAM_PROXY_SNAPSHOT_JSON = {
    'node_id': 'node-mtproxy',
    'url': 'http://node-agent:8000',
    'token': 'node-agent-token',
    'desired': {
        'enabled': True,
        'secret': '0123456789abcdef0123456789abcdef',
        'port': 8443,
        'public_host': 'proxy.example.com',
        'tls_domain': 'cloudsyncpro.net',
    },
}

EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON = {'status': 'ready', 'ready': True}
EXPECTED_TELEGRAM_PROXY_ACTIVE_RESULT_JSON = {'status': 'active', 'ready': True}
EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON = {'status': 'disabled', 'ready': False}
EXPECTED_TELEGRAM_PROXY_FAILED_RESULT_JSON = {'status': 'failed', 'ready': False}


async def test_worker_snapshot_includes_decrypted_secret_and_node_agent_fields(
    client: AsyncClient,
    db,
    worker_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    # Given: Telegram proxy is enabled for a node and the secret is stored encrypted.
    monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
    secret = '0123456789abcdef0123456789abcdef'
    node = Node(
        id='node-mtproxy',
        name='mtproxy-node',
        url='http://node-agent:8000',
        token='node-agent-token',  # noqa: S106
        server_endpoint='proxy.example.com:51820',
    )
    settings = TelegramProxySettings(
        enabled=True,
        port=8443,
        secret_encrypted=encrypt(secret),
        primary_node_id=node.id,
    )
    db.add_all([node, settings])
    await db.commit()

    # When: the worker fetches the per-node MTProxy snapshot.
    response = await client.get(
        f'/internal/worker/telegram-proxy/nodes/{node.id}/snapshot',
        headers=worker_headers,
    )

    # Then: only the worker response contains the decrypted secret and node-agent credentials.
    assert response.status_code == HTTPStatus.OK
    assert secret == EXPECTED_TELEGRAM_PROXY_SNAPSHOT_JSON['desired']['secret']
    assert response.json() == EXPECTED_TELEGRAM_PROXY_SNAPSHOT_JSON


async def test_worker_snapshot_rejects_missing_or_invalid_token_without_secret(
    client: AsyncClient,
    db,
    monkeypatch: pytest.MonkeyPatch,
):
    # Given: a valid encrypted MTProxy secret exists.
    monkeypatch.setenv('WORKER_TOKEN', 'worker-secret')
    monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
    secret = 'fedcba9876543210fedcba9876543210'
    node = Node(
        id='node-mtproxy',
        name='mtproxy-node',
        url='http://node-agent:8000',
        token='token',  # noqa: S106
    )
    db.add_all(
        [
            node,
            TelegramProxySettings(
                enabled=True,
                port=443,
                secret_encrypted=encrypt(secret),
                primary_node_id=node.id,
            ),
        ]
    )
    await db.commit()

    # When: requests omit or use the wrong worker bearer token.
    missing = await client.get(f'/internal/worker/telegram-proxy/nodes/{node.id}/snapshot')
    wrong = await client.get(
        f'/internal/worker/telegram-proxy/nodes/{node.id}/snapshot',
        headers={'Authorization': 'Bearer wrong'},
    )

    # Then: both are unauthorized and neither response leaks the secret.
    assert missing.status_code == HTTPStatus.UNAUTHORIZED
    assert wrong.status_code == HTTPStatus.UNAUTHORIZED
    assert secret not in missing.text
    assert secret not in wrong.text


async def test_worker_result_success_updates_state_and_primary_readiness(
    client: AsyncClient,
    db,
    worker_headers,
):
    # Given: a configured primary node has no MTProxy readiness state yet.
    node = Node(id='node-primary', name='primary', url='http://node-agent:8000', token='token')  # noqa: S106
    db.add_all([node, TelegramProxySettings(enabled=True, primary_node_id=node.id)])
    await db.commit()

    # When: the worker reports a ready proxy endpoint.
    response = await client.post(
        f'/internal/worker/telegram-proxy/nodes/{node.id}/result',
        json={
            'status': 'ready',
            'public_host': 'proxy.example.com',
            'public_port': 9443,
        },
        headers=worker_headers,
    )

    # Then: state is upserted and primary link readiness becomes true.
    assert response.status_code == HTTPStatus.OK
    assert response.json() == EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON
    saved = await db.get(TelegramProxyNodeState, node.id)
    assert saved is not None
    assert saved.status == 'ready'
    assert saved.last_error is None
    assert saved.public_host == 'proxy.example.com'
    assert saved.public_port == 9443
    assert saved.last_checked_at is not None
    assert saved.last_applied_at is not None

    settings = await TelegramProxySettings.get_settings(db)
    assert await select_primary_node_state(db, settings) is saved


async def test_worker_result_failure_clears_stale_endpoint_and_primary_readiness(
    client: AsyncClient,
    db,
    worker_headers,
):
    # Given: a primary node was previously ready.
    node = Node(id='node-primary', name='primary', url='http://node-agent:8000', token='token')  # noqa: S106
    settings = TelegramProxySettings(enabled=True, primary_node_id=node.id)
    state = TelegramProxyNodeState(
        node_id=node.id,
        status='ready',
        public_host='old-proxy.example.com',
        public_port=443,
    )
    db.add_all([node, settings, state])
    await db.commit()

    # When: the worker reports a failed apply/check without an endpoint.
    response = await client.post(
        f'/internal/worker/telegram-proxy/nodes/{node.id}/result',
        json={'status': 'failed', 'error': 'supervisor failed'},
        headers=worker_headers,
    )

    # Then: stale endpoint data is cleared and the node is no longer primary-ready.
    assert response.status_code == HTTPStatus.OK
    assert response.json() == EXPECTED_TELEGRAM_PROXY_FAILED_RESULT_JSON
    await db.refresh(state)
    assert state.status == 'failed'
    assert state.last_error == 'supervisor failed'
    assert state.public_host is None
    assert state.public_port is None
    assert state.last_checked_at is not None

    assert await select_primary_node_state(db, settings) is None


async def test_worker_result_lifecycle_statuses_return_exact_json(
    client: AsyncClient,
    db,
    worker_headers,
):
    # Given: three nodes representing check-active, disable, and apply-ready outcomes.
    active_node = Node(
        id='node-active',
        name='active',
        url='http://active-agent:8000',
        token='token',  # noqa: S106
    )
    disabled_node = Node(
        id='node-disabled',
        name='disabled',
        url='http://disabled-agent:8000',
        token='token',  # noqa: S106
    )
    ready_node = Node(id='node-ready', name='ready', url='http://ready-agent:8000', token='token')  # noqa: S106
    db.add_all([active_node, disabled_node, ready_node])
    await db.commit()

    # When: the worker reports representative lifecycle results.
    active = await client.post(
        f'/internal/worker/telegram-proxy/nodes/{active_node.id}/result',
        json={'status': 'active', 'public_host': 'proxy.example.com', 'public_port': 443},
        headers=worker_headers,
    )
    disabled = await client.post(
        f'/internal/worker/telegram-proxy/nodes/{disabled_node.id}/result',
        json={'status': 'disabled'},
        headers=worker_headers,
    )
    ready = await client.post(
        f'/internal/worker/telegram-proxy/nodes/{ready_node.id}/result',
        json={'status': 'ready', 'public_host': 'proxy.example.com', 'public_port': 8443},
        headers=worker_headers,
    )

    # Then: backend response JSON exactly matches the worker contract for each lifecycle branch.
    assert active.status_code == HTTPStatus.OK
    assert active.json() == EXPECTED_TELEGRAM_PROXY_ACTIVE_RESULT_JSON
    assert disabled.status_code == HTTPStatus.OK
    assert disabled.json() == EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON
    assert ready.status_code == HTTPStatus.OK
    assert ready.json() == EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON


async def test_worker_result_rejects_malformed_status_and_missing_node(
    client: AsyncClient,
    worker_headers,
):
    # Given / When: worker submits a malformed status and a result for an unknown node.
    malformed = await client.post(
        '/internal/worker/telegram-proxy/nodes/node-missing/result',
        json={'status': 'running'},
        headers=worker_headers,
    )
    missing_node = await client.post(
        '/internal/worker/telegram-proxy/nodes/node-missing/result',
        json={'status': 'failed', 'error': 'not installed'},
        headers=worker_headers,
    )

    # Then: malformed input is rejected before state changes, and unknown nodes return 404.
    assert malformed.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert missing_node.status_code == HTTPStatus.NOT_FOUND
