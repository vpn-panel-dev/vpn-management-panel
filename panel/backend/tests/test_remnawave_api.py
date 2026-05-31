from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import AsyncOperation, RemnawaveSettings, RemnawaveUser, User


@pytest.fixture(autouse=True)
def _mock_remnawave_enqueue():
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


async def test_get_settings_unauthorized(client: AsyncClient):
    resp = await client.get('/api/remnawave/settings')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_local_traffic_settings_unauthorized(client: AsyncClient):
    resp = await client.get('/api/remnawave/local-traffic/settings')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_get_settings_empty(client: AsyncClient, auth_headers):
    resp = await client.get('/api/remnawave/settings', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['enabled'] is False
    assert data['api_token_set'] is False
    assert data['webhook_secret_set'] is False


async def test_update_settings(client: AsyncClient, auth_headers):
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
        headers=auth_headers,
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


async def test_local_traffic_settings_round_trip(client: AsyncClient, auth_headers):
    resp = await client.get('/api/remnawave/local-traffic/settings', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['raw_sample_retention_days'] == 90

    resp = await client.put(
        '/api/remnawave/local-traffic/settings',
        json={'raw_sample_retention_days': 0},
        headers=auth_headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['raw_sample_retention_days'] == 0

    resp = await client.get('/api/remnawave/local-traffic/settings', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['raw_sample_retention_days'] == 0


async def test_update_settings_preserves_secrets_when_omitted(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'api_token': 'my-secret-token'},
        headers=auth_headers,
    )
    resp = await client.put(
        '/api/remnawave/settings',
        json={'base_url': 'https://new.example.com'},
        headers=auth_headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['base_url'] == 'https://new.example.com'
    assert data['api_token_set'] is True


async def test_update_settings_clears_token(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'api_token': 'my-secret-token'},
        headers=auth_headers,
    )
    resp = await client.put(
        '/api/remnawave/settings',
        json={'clear_api_token': True},
        headers=auth_headers,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['api_token_set'] is False


async def test_update_settings_clears_webhook_secret(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'webhook_secret': 'my-webhook-secret'},
        headers=auth_headers,
    )
    resp = await client.put(
        '/api/remnawave/settings',
        json={'clear_webhook_secret': True},
        headers=auth_headers,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['webhook_secret_set'] is False


async def test_test_connection_missing_config(client: AsyncClient, auth_headers):
    resp = await client.post('/api/remnawave/test', headers=auth_headers)
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert 'base URL' in resp.json()['detail']


async def test_test_connection_success(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={
            'base_url': 'https://remnawave.example.com',
            'api_token': 'my-secret-token',
        },
        headers=auth_headers,
    )

    with patch('app.routers.remnawave.httpx.AsyncClient') as mock_client_class:
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_context = mock_client_class.return_value
        mock_client = mock_context.__aenter__.return_value
        mock_client.get = AsyncMock(return_value=mock_response)

        resp = await client.post('/api/remnawave/test', headers=auth_headers)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data['success'] is True
        assert data['error'] is None

        call_args = mock_client.get.call_args
        assert call_args[1]['headers']['Authorization'] == 'Bearer my-secret-token'
        assert 'users?start=0&size=1' in call_args[0][0]


async def test_test_connection_failure(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={
            'base_url': 'https://remnawave.example.com',
            'api_token': 'my-secret-token',
        },
        headers=auth_headers,
    )

    with patch('app.routers.remnawave.httpx.AsyncClient') as mock_client_class:
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock(side_effect=httpx.ConnectError('Connection refused'))
        mock_context = mock_client_class.return_value
        mock_client = mock_context.__aenter__.return_value
        mock_client.get = AsyncMock(return_value=mock_response)

        resp = await client.post('/api/remnawave/test', headers=auth_headers)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data['success'] is False
        assert 'Connection refused' in data['error']


async def test_trigger_sync(client: AsyncClient, auth_headers):
    resp = await client.post('/api/remnawave/sync', headers=auth_headers)
    assert resp.status_code == HTTPStatus.ACCEPTED
    data = resp.json()
    assert 'operation_id' in data
    assert '/api/operations/' in data['status_url']


async def test_trigger_sync_persists_operation(client: AsyncClient, db, auth_headers):
    resp = await client.post('/api/remnawave/sync', headers=auth_headers)
    assert resp.status_code == HTTPStatus.ACCEPTED
    operation_id = resp.json()['operation_id']

    operation = await db.get(AsyncOperation, operation_id)
    assert operation is not None
    assert operation.kind == 'remnawave_full_reconcile'
    assert operation.target_type == 'remnawave'
    assert operation.target_id is None


async def test_trigger_sync_user(client: AsyncClient, db, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'base_url': 'https://remnawave.example.com', 'enabled': True},
        headers=auth_headers,
    )

    user_uuid = '11111111-1111-4111-8111-111111111111'
    with patch('app.routers.remnawave.enqueue_remnawave_sync_user', new=AsyncMock()) as enqueue:
        resp = await client.post(f'/api/remnawave/users/{user_uuid}/sync', headers=auth_headers)

    assert resp.status_code == HTTPStatus.ACCEPTED
    assert resp.json()['operation_id']
    enqueue.assert_awaited_once()
    assert enqueue.await_args.args == (user_uuid,)
    assert 'operation_id' in enqueue.await_args.kwargs
    assert 'idempotency_key' in enqueue.await_args.kwargs

    operation = await db.scalar(
        select(AsyncOperation).where(AsyncOperation.kind == 'remnawave_sync_user')
    )
    assert operation is not None
    assert operation.target_type == 'remnawave_user'
    assert operation.target_id == user_uuid


async def test_trigger_sync_user_disabled(client: AsyncClient, db, auth_headers):
    resp = await client.post(
        '/api/remnawave/users/11111111-1111-4111-8111-111111111111/sync',
        headers=auth_headers,
    )

    assert resp.status_code == HTTPStatus.CONFLICT
    assert resp.json()['detail'] == 'Remnawave is disabled'
    assert (
        await db.scalar(select(AsyncOperation).where(AsyncOperation.kind == 'remnawave_sync_user'))
        is None
    )


async def test_trigger_sync_user_invalid_uuid(client: AsyncClient, db, auth_headers):
    resp = await client.post('/api/remnawave/users/not-a-uuid/sync', headers=auth_headers)

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert (
        await db.scalar(select(AsyncOperation).where(AsyncOperation.kind == 'remnawave_sync_user'))
        is None
    )


async def test_trigger_sync_unauthorized(client: AsyncClient):
    resp = await client.post('/api/remnawave/sync')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_trigger_sync_user_unauthorized(client: AsyncClient):
    resp = await client.post('/api/remnawave/users/11111111-1111-4111-8111-111111111111/sync')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_get_status(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'base_url': 'https://remnawave.example.com', 'enabled': True},
        headers=auth_headers,
    )
    resp = await client.get('/api/remnawave/status', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['enabled'] is True
    assert data['base_url'] == 'https://remnawave.example.com'
    assert data['last_successful_reconcile_at'] is None
    assert data['last_failed_reconcile_at'] is None
    assert data['last_error'] is None
    assert data['imported_users_count'] == 0
    assert data['pending_node_sync_count'] == 0
    assert data['last_tested_at'] is None
    assert data['last_test_status'] is None
    assert data['last_test_error'] is None


async def test_get_status_includes_reconcile_observability(client: AsyncClient, db, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'base_url': 'https://remnawave.example.com', 'enabled': True},
        headers=auth_headers,
    )

    alice = User(name='alice')
    bob = User(name='bob')
    db.add_all([alice, bob])
    await db.commit()

    db.add_all(
        [
            RemnawaveUser(
                user_id=alice.id,
                remnawave_uuid='uuid-1',
                username='alice-rw',
                status='active',
                sync_status='synced',
            ),
            RemnawaveUser(
                user_id=bob.id,
                remnawave_uuid='uuid-2',
                username='bob-rw',
                status='active',
                sync_status='stale',
            ),
        ]
    )

    successful_at = datetime(2026, 1, 1, tzinfo=UTC)
    failed_at = datetime(2026, 1, 2, tzinfo=UTC)
    db.add_all(
        [
            AsyncOperation(
                id='reconcile-success',
                kind='remnawave_full_reconcile',
                target_type='remnawave',
                target_id=None,
                status='succeeded',
                error=None,
                idempotency_key='reconcile-success-key',
                updated_at=successful_at,
                finished_at=successful_at,
            ),
            AsyncOperation(
                id='reconcile-failed',
                kind='remnawave_full_reconcile',
                target_type='remnawave',
                target_id=None,
                status='failed',
                error='sync exploded',
                idempotency_key='reconcile-failed-key',
                updated_at=failed_at,
                finished_at=failed_at,
            ),
        ]
    )

    settings = await db.scalar(select(RemnawaveSettings))
    assert settings is not None
    settings.last_synced_at = successful_at
    await db.commit()

    resp = await client.get('/api/remnawave/status', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['enabled'] is True
    assert data['base_url'] == 'https://remnawave.example.com'
    assert data['last_successful_reconcile_at'] == '2026-01-01T00:00:00'
    assert data['last_failed_reconcile_at'] == '2026-01-02T00:00:00'
    assert data['last_error'] == 'sync exploded'
    assert data['imported_users_count'] == 2
    assert data['pending_node_sync_count'] == 1
    assert data['last_tested_at'] is None
    assert data['last_test_status'] is None
    assert data['last_test_error'] is None


async def test_settings_never_returns_decrypted_token(client: AsyncClient, auth_headers):
    await client.put(
        '/api/remnawave/settings',
        json={'api_token': 'my-secret-token'},
        headers=auth_headers,
    )
    resp = await client.get('/api/remnawave/settings', headers=auth_headers)
    data = resp.json()
    assert 'api_token' not in data
    assert 'webhook_secret' not in data
    assert data['api_token_set'] is True
