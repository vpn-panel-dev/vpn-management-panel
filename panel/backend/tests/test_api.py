import asyncio
from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import (
    AsyncOperation,
    LocalAmneziawgTrafficSettings,
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Node,
    Peer,
    User,
)


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

    async def _cleanup_raw_traffic_samples(**kwargs):
        return {
            'command': 'cleanup_raw_traffic_samples',
            'operation_id': kwargs['operation_id'],
        }

    async def _remnawave_full_reconcile(**kwargs):
        return {
            'command': 'remnawave_full_reconcile',
            'operation_id': kwargs['operation_id'],
        }

    async def _remnawave_sync_user(user_uuid, **kwargs):
        return {
            'command': 'remnawave_sync_user',
            'target_id': user_uuid,
            'operation_id': kwargs['operation_id'],
        }

    async def _remnawave_disable_user(user_uuid, **kwargs):
        return {
            'command': 'remnawave_disable_user',
            'target_id': user_uuid,
            'operation_id': kwargs['operation_id'],
        }

    with (
        patch('app.routers.api.enqueue_sync_all', new=AsyncMock(side_effect=_sync_all)),
        patch('app.routers.api.enqueue_sync_node', new=AsyncMock(side_effect=_sync_node)),
        patch(
            'app.routers.api.enqueue_provision_node',
            new=AsyncMock(side_effect=_provision_node),
        ),
        patch(
            'app.routers.api.enqueue_cleanup_raw_traffic_samples',
            new=AsyncMock(side_effect=_cleanup_raw_traffic_samples),
        ),
        patch(
            'app.routers.api.enqueue_remnawave_full_reconcile',
            new=AsyncMock(side_effect=_remnawave_full_reconcile),
        ),
        patch(
            'app.routers.api.enqueue_remnawave_sync_user',
            new=AsyncMock(side_effect=_remnawave_sync_user),
        ),
        patch(
            'app.routers.api.enqueue_remnawave_disable_user',
            new=AsyncMock(side_effect=_remnawave_disable_user),
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
    assert peers_resp.json()[0]['online'] is False
    assert peers_resp.json()[0]['endpoint'] is None


async def test_create_pending_peers_is_idempotent(client: AsyncClient, auth_headers, db):
    headers = auth_headers
    await client.post('/api/users', json={'name': 'alice'}, headers=headers)
    node_resp = await client.post(
        '/api/nodes',
        json={'name': 'node-idem', 'url': 'http://agent-idem:8000', 'token': 'tok'},
        headers=headers,
    )
    node = await db.get(Node, node_resp.json()['id'])
    user = (await db.execute(select(User).where(User.name == 'alice'))).scalar_one()

    from app.services.users import create_pending_peers_for_node, create_pending_peers_for_user

    await create_pending_peers_for_node(db, node)
    await create_pending_peers_for_user(db, user)
    await db.commit()

    peers = (
        (await db.execute(select(Peer).where(Peer.node_id == node.id, Peer.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(peers) == 1


async def test_create_pending_peers_for_user_is_concurrency_safe(db):
    node = Node(
        id='node-race',
        name='node-race',
        url='http://agent:8000',
        token='tok',  # noqa: S106
    )
    user = User(
        id='user-race',
        name='alice-race',
        public_key='alice-race-public',
        private_key='alice-race-private',
        vpn_ip='10.8.0.2',
    )
    db.add_all([node, user])
    await db.commit()

    session_factory = async_sessionmaker(bind=db.bind, expire_on_commit=False)

    from app.services.users import create_pending_peers_for_user

    async def create_once() -> set[str]:
        async with session_factory() as session:
            loaded_user = await session.get(User, user.id)
            created = await create_pending_peers_for_user(session, loaded_user)
            await session.commit()
            return created

    first, second = await asyncio.gather(create_once(), create_once())

    peers = (
        (await db.execute(select(Peer).where(Peer.node_id == node.id, Peer.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(peers) == 1
    assert sorted([first, second], key=len) == [set(), {node.id}]


async def test_create_pending_peers_for_node_is_concurrency_safe(db):
    node = Node(
        id='node-race-2',
        name='node-race-2',
        url='http://agent:8000',
        token='tok',  # noqa: S106
    )
    user = User(
        id='user-race-2',
        name='alice-race-2',
        public_key='alice-race-2-public',
        private_key='alice-race-2-private',
        vpn_ip='10.8.0.3',
    )
    db.add_all([node, user])
    await db.commit()

    session_factory = async_sessionmaker(bind=db.bind, expire_on_commit=False)

    from app.services.users import create_pending_peers_for_node

    async def create_once() -> set[str]:
        async with session_factory() as session:
            loaded_node = await session.get(Node, node.id)
            created = await create_pending_peers_for_node(session, loaded_node)
            await session.commit()
            return created

    first, second = await asyncio.gather(create_once(), create_once())

    peers = (
        (await db.execute(select(Peer).where(Peer.node_id == node.id, Peer.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(peers) == 1
    assert sorted([first, second], key=len) == [set(), {user.id}]


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
        assert 'online_peers_count' in node
        assert node['online_threshold_seconds'] == 180
    # Should have our just-created node
    assert any(n['name'] == 'n-list' for n in data)


async def test_list_nodes_online_uses_heartbeat_reachability(client: AsyncClient, auth_headers, db):
    node = Node(
        id='reachable-node',
        name='reachable-node',
        url='http://agent:8000',
        token='tok',  # noqa: S106
        health_status='offline',
        reachability_status='reachable',
    )
    db.add(node)
    await db.commit()

    resp = await client.get('/api/nodes', headers=auth_headers)

    assert resp.status_code == HTTPStatus.OK
    listed = next(item for item in resp.json() if item['id'] == 'reachable-node')
    assert listed['online'] is True
    assert listed['reachable'] is True


async def test_list_operations_exposes_resolution_state(client: AsyncClient, auth_headers, db):
    failed = AsyncOperation(
        id='op-failed',
        kind='sync_node',
        target_type='node',
        target_id='node-1',
        status='failed',
        error='node-agent unavailable',
        idempotency_key='failed-key',
    )
    timed_out = AsyncOperation(
        id='op-timeout',
        kind='provision_node',
        target_type='node',
        target_id='node-2',
        status='failed_by_timeout',
        error='Operation exceeded running timeout and needs manual action',
        idempotency_key='timeout-key',
    )
    db.add_all([failed, timed_out])
    await db.commit()

    resp = await client.get('/api/operations', headers=auth_headers)

    assert resp.status_code == HTTPStatus.OK
    data = {item['id']: item for item in resp.json()}
    assert data['op-failed']['resolution_state'] == 'recoverable'
    assert data['op-failed']['can_retry'] is True
    assert data['op-timeout']['resolution_state'] == 'needs_manual_action'
    assert data['op-timeout']['can_retry'] is True


async def test_retry_failed_operation_creates_new_operation(client: AsyncClient, auth_headers, db):
    operation = AsyncOperation(
        id='retry-source',
        kind='sync_node',
        target_type='node',
        target_id='node-1',
        status='failed_by_timeout',
        error='Operation exceeded running timeout and needs manual action',
        idempotency_key='retry-source-key',
    )
    db.add(operation)
    await db.commit()

    resp = await client.post('/api/operations/retry-source/retry', headers=auth_headers)

    assert resp.status_code == HTTPStatus.ACCEPTED
    payload = resp.json()
    retried = await db.get(AsyncOperation, payload['operation_id'])
    assert retried is not None
    assert retried.id != operation.id
    assert retried.kind == 'sync_node'
    assert retried.target_id == 'node-1'
    assert retried.status == 'queued'


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
    assert dave['online'] is False
    assert len(dave['peers']) >= 1
    assert dave['peers'][0]['online'] is False
    assert dave['peers'][0]['endpoint'] is None


async def test_online_fields_are_derived_from_peer_handshake(client: AsyncClient, auth_headers, db):
    threshold_settings = await LocalAmneziawgTrafficSettings.get_settings(db)
    threshold_settings.peer_online_threshold_seconds = 600
    now = datetime.now(UTC)
    node = Node(id='online-node', name='online-node', url='http://agent:8000', token='tok')  # noqa: S106
    user = User(id='online-user', name='online-user')
    peer = Peer(
        id='online-peer',
        node_id=node.id,
        user_id=user.id,
        status='active',
        last_handshake=now - timedelta(seconds=60),
        endpoint='203.0.113.10:54321',
    )
    db.add_all([node, user, peer])
    await db.commit()

    users_resp = await client.get('/api/users', headers=auth_headers)
    nodes_resp = await client.get('/api/nodes', headers=auth_headers)
    peers_resp = await client.get(f'/api/nodes/{node.id}/peers', headers=auth_headers)

    assert users_resp.status_code == HTTPStatus.OK
    assert nodes_resp.status_code == HTTPStatus.OK
    assert peers_resp.status_code == HTTPStatus.OK
    listed_user = next(row for row in users_resp.json() if row['id'] == user.id)
    listed_node = next(row for row in nodes_resp.json() if row['id'] == node.id)
    assert listed_user['online'] is True
    assert listed_user['peers'][0]['online'] is True
    assert listed_user['peers'][0]['endpoint'] == '203.0.113.10:54321'
    assert listed_node['online_peers_count'] == 1
    assert listed_node['online_threshold_seconds'] == 600
    assert peers_resp.json()[0]['online'] is True
    assert peers_resp.json()[0]['endpoint'] == '203.0.113.10:54321'


async def test_online_fields_tolerate_duplicate_settings_rows(
    client: AsyncClient, auth_headers, db
):
    db.add_all(
        [
            LocalAmneziawgTrafficSettings(peer_online_threshold_seconds=120),
            LocalAmneziawgTrafficSettings(peer_online_threshold_seconds=240),
        ]
    )
    await db.commit()

    users_resp = await client.get('/api/users', headers=auth_headers)
    nodes_resp = await client.get('/api/nodes', headers=auth_headers)

    assert users_resp.status_code == HTTPStatus.OK
    assert nodes_resp.status_code == HTTPStatus.OK


async def test_list_users_includes_local_traffic_summary(client: AsyncClient, auth_headers, db):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'local-list'}, headers=headers)
    user_id = user_resp.json()['id']
    updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=120,
            tx_bytes=80,
            total_bytes=200,
            updated_at=updated_at,
        )
    )
    await db.commit()

    resp = await client.get('/api/users', headers=headers)

    assert resp.status_code == HTTPStatus.OK
    user = next(row for row in resp.json() if row['id'] == user_id)
    assert user['local_traffic'] == {
        'source': 'local_amneziawg',
        'user_id': user_id,
        'rx_bytes': 120,
        'tx_bytes': 80,
        'total_bytes': 200,
        'updated_at': '2026-01-02T03:04:05',
    }


async def test_trigger_sync_enqueues_cleanup_operation(client: AsyncClient, auth_headers, db):
    resp = await client.post('/api/sync', headers=auth_headers)

    assert resp.status_code == HTTPStatus.ACCEPTED
    data = resp.json()
    assert data['operation_id']
    assert data['status_url'] == f'/api/operations/{data["operation_id"]}'

    operations = (await db.execute(select(AsyncOperation))).scalars().all()
    assert {operation.kind for operation in operations} == {
        'sync_all',
        'cleanup_raw_traffic_samples',
    }
    assert {operation.target_type for operation in operations} == {'all', 'traffic'}


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


async def test_user_local_traffic_requires_auth(client: AsyncClient, auth_headers):
    user_resp = await client.post('/api/users', json={'name': 'local-auth'}, headers=auth_headers)
    user_id = user_resp.json()['id']

    resp = await client.get(f'/api/users/{user_id}/local-traffic')

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_user_local_traffic_lifetime_zero_for_no_data(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'local-empty'}, headers=headers)
    user_id = user_resp.json()['id']

    resp = await client.get(f'/api/users/{user_id}/local-traffic', headers=headers)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'source': 'local_amneziawg',
        'user_id': user_id,
        'rx_bytes': 0,
        'tx_bytes': 0,
        'total_bytes': 0,
        'updated_at': None,
    }


async def test_user_local_traffic_returns_lifetime_daily_and_node_breakdowns(
    client: AsyncClient,
    auth_headers,
    db,
):
    headers = auth_headers
    today = date.today()
    yesterday = today - timedelta(days=1)
    updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    node = Node(
        id='node-local-1',
        name='local-node',
        url='http://agent:8000',
        token='tok',  # noqa: S106
    )
    user = User(
        id='user-local-1',
        name='local-usage',
        public_key='user-public',
        private_key='user-private',
        vpn_ip='10.8.0.2',
    )
    peer = Peer(id='peer-local-1', node_id=node.id, user_id=user.id, status='active')
    db.add_all(
        [
            node,
            user,
            peer,
            LocalAmneziawgUserLifetimeTraffic(
                user_id=user.id,
                rx_bytes=100,
                tx_bytes=250,
                total_bytes=350,
                updated_at=updated_at,
            ),
            LocalAmneziawgUserDailyTraffic(
                user_id=user.id,
                day=today,
                rx_bytes=40,
                tx_bytes=60,
                total_bytes=100,
                updated_at=updated_at,
            ),
            LocalAmneziawgUserDailyTraffic(
                user_id=user.id,
                day=yesterday,
                rx_bytes=60,
                tx_bytes=190,
                total_bytes=250,
                updated_at=updated_at,
            ),
            LocalAmneziawgUserNodeLifetimeTraffic(
                user_id=user.id,
                node_id=node.id,
                rx_bytes=100,
                tx_bytes=250,
                total_bytes=350,
                updated_at=updated_at,
            ),
            LocalAmneziawgUserNodeDailyTraffic(
                user_id=user.id,
                node_id=node.id,
                day=today,
                rx_bytes=40,
                tx_bytes=60,
                total_bytes=100,
                updated_at=updated_at,
            ),
        ]
    )
    await db.commit()

    lifetime_resp = await client.get(f'/api/users/{user.id}/local-traffic', headers=headers)
    daily_resp = await client.get(
        f'/api/users/{user.id}/local-traffic/daily?days=30', headers=headers
    )
    node_resp = await client.get(f'/api/users/{user.id}/local-traffic/nodes', headers=headers)
    node_daily_resp = await client.get(
        f'/api/users/{user.id}/local-traffic/nodes/daily?days=30', headers=headers
    )

    assert lifetime_resp.status_code == HTTPStatus.OK
    assert lifetime_resp.json()['source'] == 'local_amneziawg'
    assert lifetime_resp.json()['rx_bytes'] == 100
    assert lifetime_resp.json()['tx_bytes'] == 250
    assert lifetime_resp.json()['total_bytes'] == 350
    assert daily_resp.status_code == HTTPStatus.OK
    assert [row['day'] for row in daily_resp.json()] == [yesterday.isoformat(), today.isoformat()]
    assert all(row['source'] == 'local_amneziawg' for row in daily_resp.json())
    assert {row['total_bytes'] for row in daily_resp.json()} == {100, 250}
    assert node_resp.status_code == HTTPStatus.OK
    assert node_resp.json()[0]['source'] == 'local_amneziawg'
    assert node_resp.json()[0]['node_id'] == node.id
    assert node_resp.json()[0]['node_name'] == node.name
    assert node_resp.json()[0]['total_bytes'] == 350
    assert node_daily_resp.status_code == HTTPStatus.OK
    assert node_daily_resp.json() == [
        {
            'source': 'local_amneziawg',
            'user_id': user.id,
            'day': today.isoformat(),
            'rx_bytes': 40,
            'tx_bytes': 60,
            'total_bytes': 100,
            'updated_at': '2026-01-02T03:04:05',
            'node_id': node.id,
            'node_name': node.name,
        }
    ]


async def test_node_local_traffic_returns_all_user_totals(client: AsyncClient, auth_headers, db):
    headers = auth_headers
    updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    node = Node(
        id='node-total-1',
        name='aggregate-node',
        url='http://agent:8000',
        token='tok',  # noqa: S106
    )
    other_node = Node(
        id='node-total-2',
        name='other-node',
        url='http://agent-2:8000',
        token='tok-2',  # noqa: S106
    )
    first_user = User(id='node-user-1', name='node-user-1')
    second_user = User(id='node-user-2', name='node-user-2')
    db.add_all(
        [
            node,
            other_node,
            first_user,
            second_user,
            LocalAmneziawgUserNodeLifetimeTraffic(
                user_id=first_user.id,
                node_id=node.id,
                rx_bytes=100,
                tx_bytes=250,
                total_bytes=350,
                updated_at=updated_at,
            ),
            LocalAmneziawgUserNodeLifetimeTraffic(
                user_id=second_user.id,
                node_id=node.id,
                rx_bytes=10,
                tx_bytes=20,
                total_bytes=30,
                updated_at=updated_at + timedelta(seconds=1),
            ),
            LocalAmneziawgUserNodeLifetimeTraffic(
                user_id=second_user.id,
                node_id=other_node.id,
                rx_bytes=999,
                tx_bytes=999,
                total_bytes=1998,
                updated_at=updated_at,
            ),
        ]
    )
    await db.commit()

    resp = await client.get(f'/api/nodes/{node.id}/local-traffic', headers=headers)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'source': 'local_amneziawg',
        'node_id': node.id,
        'node_name': node.name,
        'rx_bytes': 110,
        'tx_bytes': 270,
        'total_bytes': 380,
        'updated_at': '2026-01-02T03:04:06',
    }


async def test_node_local_traffic_zero_for_no_data(client: AsyncClient, auth_headers, db):
    node = Node(
        id='node-total-empty',
        name='empty-node',
        url='http://agent:8000',
        token='tok',  # noqa: S106
    )
    db.add(node)
    await db.commit()

    resp = await client.get(f'/api/nodes/{node.id}/local-traffic', headers=auth_headers)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'source': 'local_amneziawg',
        'node_id': node.id,
        'node_name': node.name,
        'rx_bytes': 0,
        'tx_bytes': 0,
        'total_bytes': 0,
        'updated_at': None,
    }


async def test_user_traffic_endpoint_keeps_existing_shape(client: AsyncClient, auth_headers):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'legacy-traffic'}, headers=headers)
    user_id = user_resp.json()['id']

    resp = await client.get(f'/api/users/{user_id}/traffic?days=30', headers=headers)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == []


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
    data = resp.json()
    assert data['blocked'] is True
    assert data['status'] == {'code': 'blocked', 'reason': 'blocked'}
    assert data['subscription'] == {
        'managed': False,
        'expire_at': None,
        'last_synced_at': None,
    }
    assert data['traffic'] == {
        'used_bytes': 0,
        'limit_bytes': None,
        'local_used_bytes': 0,
        'remote_used_bytes': 0,
        'updated_at': None,
    }
    assert data['updated_at'] is None


async def test_pub_user_info_active(client: AsyncClient, auth_headers, db):
    headers = auth_headers
    user_resp = await client.post('/api/users', json={'name': 'active-user'}, headers=headers)
    user_id = user_resp.json()['id']
    updated_at = datetime(2026, 1, 2, 3, 4, 6)
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=120,
            tx_bytes=340,
            total_bytes=460,
            updated_at=updated_at,
        )
    )
    await db.commit()

    resp = await client.get(f'/pub/u/{user_id}/info')
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['blocked'] is False
    assert data['user_name'] == 'active-user'
    assert data['status'] == {'code': 'active', 'reason': None}
    assert data['subscription'] == {
        'managed': False,
        'expire_at': None,
        'last_synced_at': None,
    }
    assert data['traffic'] == {
        'used_bytes': 460,
        'limit_bytes': None,
        'local_used_bytes': 460,
        'remote_used_bytes': 0,
        'updated_at': '2026-01-02T03:04:06',
    }
    assert data['updated_at'] == '2026-01-02T03:04:06'


async def test_pub_qr_not_found(client: AsyncClient):
    resp = await client.get('/pub/u/nonexistent/qr/awg/nonexistent')
    assert resp.status_code == HTTPStatus.NOT_FOUND
