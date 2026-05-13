from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _mock_job_producer():
    """Mock RabbitMQ producers so API tests don't need a live broker."""

    async def _sync_all(**kwargs):
        return {'command': 'sync_all', 'operation_id': kwargs['operation_id']}

    async def _sync_node(node_id, **kwargs):
        return {
            'command': 'sync_node',
            'target_id': node_id,
            'operation_id': kwargs['operation_id'],
        }

    async def _provision_node(node_id, **kwargs):
        return {
            'command': 'provision_node',
            'target_id': node_id,
            'operation_id': kwargs['operation_id'],
        }

    with (
        patch('app.routers.api.enqueue_sync_all', new=AsyncMock(side_effect=_sync_all)),
        patch('app.routers.api.enqueue_sync_node', new=AsyncMock(side_effect=_sync_node)),
        patch(
            'app.routers.api.enqueue_provision_node',
            new=AsyncMock(side_effect=_provision_node),
        ),
    ):
        yield


# ── Nodes ──────────────────────────────────────────────────────────────────────


async def test_list_nodes_empty(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.get('/api/nodes', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []


async def test_add_node(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.post(
        '/api/nodes',
        json={'name': 'node-1', 'url': 'http://agent:8000', 'token': 'tok'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['name'] == 'node-1'
    assert data['url'] == 'http://agent:8000'
    assert data['server_public_key'] is not None
    assert data['listen_port'] == 51820


async def test_add_node_creates_peers_for_existing_users(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.post('/api/users', json={'name': 'alice'}, headers=headers)
    resp = await client.post(
        '/api/nodes',
        json={'name': 'node-2', 'url': 'http://agent2:8000', 'token': 'tok'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.CREATED
    node_id = resp.json()['id']
    peers_resp = await client.get(f'/api/nodes/{node_id}/peers', headers=headers)
    assert peers_resp.status_code == HTTPStatus.OK
    assert len(peers_resp.json()) == 1
    assert peers_resp.json()[0]['user_name'] == 'alice'


async def test_list_nodes_after_create(client: AsyncClient, auth_headers):
    headers = auth_headers
    # Create a node in this same test (DB is reset between tests)
    await client.post(
        '/api/nodes',
        json={'name': 'n-list', 'url': 'http://agent:8000', 'token': 'tok'},
        headers=headers,
    )
    resp = await client.get('/api/nodes', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert len(data) >= 1
    for node in data:
        assert 'online' in node
    # Should have our just-created node
    assert any(n['name'] == 'n-list' for n in data)


async def test_update_node(client: AsyncClient, auth_headers):
    headers = auth_headers
    create_resp = await client.post(
        '/api/nodes',
        json={'name': 'node-update', 'url': 'http://agent:8000', 'token': 'tok'},
        headers=headers,
    )
    node_id = create_resp.json()['id']

    resp = await client.patch(
        f'/api/nodes/{node_id}',
        json={'jc': 10, 'jmin': 50, 'jmax': 100},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['jc'] == 10


async def test_update_nonexistent_node(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.patch(
        '/api/nodes/nonexistent-id',
        json={'jc': 10},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_delete_node(client: AsyncClient, auth_headers):
    headers = auth_headers
    create_resp = await client.post(
        '/api/nodes',
        json={'name': 'node-delete', 'url': 'http://agent:8000', 'token': 'tok'},
        headers=headers,
    )
    node_id = create_resp.json()['id']

    resp = await client.delete(f'/api/nodes/{node_id}', headers=headers)
    assert resp.status_code == HTTPStatus.NO_CONTENT

    list_resp = await client.get('/api/nodes', headers=headers)
    assert all(n['id'] != node_id for n in list_resp.json())


async def test_delete_nonexistent_node(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.delete('/api/nodes/nonexistent-id', headers=headers)
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_provision_node(client: AsyncClient, auth_headers):
    headers = auth_headers
    create_resp = await client.post(
        '/api/nodes',
        json={'name': 'node-prov', 'url': 'http://agent:8000', 'token': 'tok'},
        headers=headers,
    )
    node_id = create_resp.json()['id']
    resp = await client.post(f'/api/nodes/{node_id}/provision', headers=headers)
    assert resp.status_code == HTTPStatus.ACCEPTED
    data = resp.json()
    assert data['operation_id']
    assert data['status_url'] == f'/api/operations/{data["operation_id"]}'


# ── Users ──────────────────────────────────────────────────────────────────────


async def test_list_users_empty(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.get('/api/users', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []


async def test_add_user(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.post('/api/users', json={'name': 'bob'}, headers=headers)
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['name'] == 'bob'
    assert data['public_key'] is not None
    assert data['vpn_ip'] is not None
    assert not data['is_blocked']


async def test_add_user_with_name(client: AsyncClient, auth_headers):
    """Verify user is created with correct fields."""
    headers = auth_headers
    resp = await client.post('/api/users', json={'name': 'test-name'}, headers=headers)
    assert resp.status_code == HTTPStatus.CREATED
    data = resp.json()
    assert data['name'] == 'test-name'
    assert data['public_key'] is not None
    assert data['vpn_ip'] is not None
    assert data['is_blocked'] is False


async def test_list_users_with_peers(client: AsyncClient, auth_headers):
    headers = auth_headers
    await client.post(
        '/api/nodes',
        json={'name': 'n1', 'url': 'http://agent:8000', 'token': 'tok'},
        headers=headers,
    )
    await client.post('/api/users', json={'name': 'dave'}, headers=headers)

    resp = await client.get('/api/users', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()
    assert len(users) >= 1
    dave = next(u for u in users if u['name'] == 'dave')
    assert dave['public_key'] is not None
    assert dave['vpn_ip'] is not None
    assert len(dave['peers']) >= 1


async def test_block_user(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'block-me'}, headers=headers)
    user_id = user_resp.json()['id']

    resp = await client.put(f'/api/users/{user_id}/block', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['is_blocked'] is True


async def test_unblock_user(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'unblock-me'}, headers=headers)
    user_id = user_resp.json()['id']

    await client.put(f'/api/users/{user_id}/block', headers=headers)
    resp = await client.put(f'/api/users/{user_id}/unblock', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['is_blocked'] is False


async def test_block_nonexistent_user(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.put('/api/users/nonexistent/block', headers=headers)
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_delete_user(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'delete-me'}, headers=headers)
    user_id = user_resp.json()['id']

    resp = await client.delete(f'/api/users/{user_id}', headers=headers)
    assert resp.status_code == HTTPStatus.NO_CONTENT


# ── Configs ────────────────────────────────────────────────────────────────────


async def test_user_configs_requires_keypair(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.get('/api/users/nonexistent/configs', headers=headers)
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_trigger_sync(client: AsyncClient, auth_headers):
    headers = auth_headers
    resp = await client.post('/api/sync', headers=headers)
    assert resp.status_code == HTTPStatus.ACCEPTED
    data = resp.json()
    assert data['operation_id']
    assert data['status_url'] == f'/api/operations/{data["operation_id"]}'


async def test_get_operation(client: AsyncClient, auth_headers):
    headers = auth_headers
    sync_resp = await client.post('/api/sync', headers=headers)
    operation_id = sync_resp.json()['operation_id']

    resp = await client.get(f'/api/operations/{operation_id}', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['id'] == operation_id
    assert data['kind'] == 'sync_all'
    assert data['status'] == 'queued'


# ── User page (public, no auth) ────────────────────────────────────────────────


async def test_pub_user_info_not_found(client: AsyncClient):
    resp = await client.get('/pub/u/nonexistent/info')
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_pub_user_info_blocked(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'blocked-user'}, headers=headers)
    user_id = user_resp.json()['id']
    await client.put(f'/api/users/{user_id}/block', headers=headers)

    resp = await client.get(f'/pub/u/{user_id}/info')
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['blocked'] is True


async def test_pub_user_info_active(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'active-user'}, headers=headers)
    user_id = user_resp.json()['id']

    resp = await client.get(f'/pub/u/{user_id}/info')
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['blocked'] is False
    assert resp.json()['user_name'] == 'active-user'


async def test_pub_qr_not_found(client: AsyncClient):
    resp = await client.get('/pub/u/nonexistent/qr/awg/nonexistent')
    assert resp.status_code == HTTPStatus.NOT_FOUND
