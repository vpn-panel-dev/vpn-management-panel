from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _mock_remnawave_enqueue():
    """Mock RabbitMQ producer for remnawave sync so tests don't need a live broker."""

    async def _enqueue(**kwargs):
        return {
            'command': 'remnawave_full_reconcile',
            'operation_id': kwargs['operation_id'],
        }

    with patch(
        'app.routers.remnawave.enqueue_remnawave_full_reconcile',
        new=AsyncMock(side_effect=_enqueue),
    ):
        yield


# ── Settings ───────────────────────────────────────────────────────────────────


async def test_get_settings_unauthorized(client: AsyncClient):
    resp = await client.get('/api/remnawave/settings')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_get_settings_empty(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.get('/api/remnawave/settings', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['enabled'] is False
    assert data['api_token_set'] is False
    assert data['webhook_secret_set'] is False


async def test_update_settings(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.put(
        '/api/remnawave/settings',
        json={
            'base_url': 'https://remnawave.example.com',
            'enabled': True,
            'polling_enabled': True,
            'polling_interval_seconds': 600,
            'api_token': 'my-secret-token',
            'webhook_secret': 'my-webhook-secret',
            'subscription_url': 'https://sub.example.com',
        },
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['base_url'] == 'https://remnawave.example.com'
    assert data['enabled'] is True
    assert data['polling_enabled'] is True
    assert data['polling_interval_seconds'] == 600
    assert data['api_token_set'] is True
    assert data['webhook_secret_set'] is True
    assert data['subscription_url'] == 'https://sub.example.com'


async def test_update_settings_preserves_secrets_when_omitted(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={'api_token': 'my-secret-token'},
        headers=headers,
    )
    resp = await client.put(
        '/api/remnawave/settings',
        json={'base_url': 'https://new.example.com'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['base_url'] == 'https://new.example.com'
    assert data['api_token_set'] is True


async def test_update_settings_clears_token(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={'api_token': 'my-secret-token'},
        headers=headers,
    )
    resp = await client.put(
        '/api/remnawave/settings',
        json={'clear_api_token': True},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['api_token_set'] is False


async def test_update_settings_clears_webhook_secret(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={'webhook_secret': 'my-webhook-secret'},
        headers=headers,
    )
    resp = await client.put(
        '/api/remnawave/settings',
        json={'clear_webhook_secret': True},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['webhook_secret_set'] is False


# ── Test Connection ────────────────────────────────────────────────────────────


async def test_test_connection_missing_config(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.post('/api/remnawave/test', headers=headers)
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert 'base URL' in resp.json()['detail']


async def test_test_connection_success(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={
            'base_url': 'https://remnawave.example.com',
            'api_token': 'my-secret-token',
        },
        headers=headers,
    )

    with patch('app.routers.remnawave.httpx.AsyncClient') as mock_client_class:
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_context = mock_client_class.return_value
        mock_client = mock_context.__aenter__.return_value
        mock_client.get = AsyncMock(return_value=mock_response)

        resp = await client.post('/api/remnawave/test', headers=headers)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data['success'] is True
        assert data['error'] is None

        call_args = mock_client.get.call_args
        assert call_args[1]['headers']['Authorization'] == 'Bearer my-secret-token'
        assert 'users?start=0&size=1' in call_args[0][0]


async def test_test_connection_failure(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={
            'base_url': 'https://remnawave.example.com',
            'api_token': 'my-secret-token',
        },
        headers=headers,
    )

    with patch('app.routers.remnawave.httpx.AsyncClient') as mock_client_class:
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock(side_effect=httpx.ConnectError('Connection refused'))
        mock_context = mock_client_class.return_value
        mock_client = mock_context.__aenter__.return_value
        mock_client.get = AsyncMock(return_value=mock_response)

        resp = await client.post('/api/remnawave/test', headers=headers)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data['success'] is False
        assert 'Connection refused' in data['error']


# ── Sync ───────────────────────────────────────────────────────────────────────


async def test_trigger_sync(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.post('/api/remnawave/sync', headers=headers)
    assert resp.status_code == HTTPStatus.ACCEPTED
    data = resp.json()
    assert 'operation_id' in data
    assert '/api/operations/' in data['status_url']


async def test_trigger_sync_unauthorized(client: AsyncClient):
    resp = await client.post('/api/remnawave/sync')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ── Status ─────────────────────────────────────────────────────────────────────


async def test_get_status(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={'base_url': 'https://remnawave.example.com', 'enabled': True},
        headers=headers,
    )
    resp = await client.get('/api/remnawave/status', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['enabled'] is True
    assert data['base_url'] == 'https://remnawave.example.com'
    assert data['last_tested_at'] is None
    assert data['last_test_status'] is None


async def test_get_status_unauthorized(client: AsyncClient):
    resp = await client.get('/api/remnawave/status')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ── Secrets never exposed ──────────────────────────────────────────────────────


async def test_settings_never_returns_decrypted_token(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.put(
        '/api/remnawave/settings',
        json={'api_token': 'my-secret-token'},
        headers=headers,
    )
    resp = await client.get('/api/remnawave/settings', headers=headers)
    data = resp.json()
    assert 'api_token' not in data
    assert 'webhook_secret' not in data
    assert data['api_token_set'] is True
