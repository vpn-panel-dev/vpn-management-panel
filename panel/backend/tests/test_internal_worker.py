from datetime import UTC, datetime, timedelta
from http import HTTPStatus

from httpx import AsyncClient
from sqlalchemy import select

from app.models import AsyncOperation, Node, Peer, PeerTrafficSample


async def test_worker_auth_rejects_missing_or_wrong_token(client: AsyncClient, monkeypatch):
    monkeypatch.setenv('WORKER_TOKEN', 'worker-secret')

    missing = await client.get('/internal/worker/sync/snapshot')
    wrong = await client.get(
        '/internal/worker/sync/snapshot',
        headers={'Authorization': 'Bearer wrong'},
    )

    assert missing.status_code == HTTPStatus.UNAUTHORIZED
    assert wrong.status_code == HTTPStatus.UNAUTHORIZED


async def test_operation_lifecycle_and_stale_filter(client: AsyncClient, db, worker_headers):
    old = datetime.now(UTC) - timedelta(seconds=60)
    queued = AsyncOperation(
        id='operation-queued',
        kind='sync_node',
        target_type='node',
        target_id='node-1',
        status='queued',
        idempotency_key='queued-key',
        updated_at=old,
    )
    fresh = AsyncOperation(
        id='operation-fresh',
        kind='sync_node',
        target_type='node',
        target_id='node-2',
        status='queued',
        idempotency_key='fresh-key',
    )
    db.add_all([queued, fresh])
    await db.commit()

    stale = await client.get(
        '/internal/worker/operations/stale?status=queued&older_than_seconds=30',
        headers=worker_headers,
    )
    started = await client.post(
        '/internal/worker/operations/operation-queued/start',
        headers=worker_headers,
    )
    conflict = await client.post(
        '/internal/worker/operations/operation-queued/succeed',
        json={'result': {'ok': True}},
        headers=worker_headers,
    )

    assert stale.status_code == HTTPStatus.OK
    assert [operation['id'] for operation in stale.json()['operations']] == ['operation-queued']
    assert started.status_code == HTTPStatus.OK
    assert started.json() == {'status': 'running', 'attempts': 1}
    assert conflict.status_code == HTTPStatus.OK

    saved = await db.get(AsyncOperation, 'operation-queued')
    await db.refresh(saved)
    assert saved.status == 'succeeded'
    assert saved.result == '{"ok": true}'
    assert saved.finished_at is not None


async def test_snapshots_include_worker_fields(
    client: AsyncClient, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state

    sync = await client.get(
        f'/internal/worker/nodes/{node.id}/sync-snapshot', headers=worker_headers
    )
    provision = await client.get(
        f'/internal/worker/nodes/{node.id}/provision-snapshot',
        headers=worker_headers,
    )
    all_nodes = await client.get('/internal/worker/sync/snapshot', headers=worker_headers)

    assert sync.status_code == HTTPStatus.OK
    assert sync.json()['url'] == 'http://agent:8000'
    assert sync.json()['token'] == 'node-token'
    assert sync.json()['interface']['private_key'] == 'node-private'
    assert sync.json()['peers'] == [
        {
            'peer_id': peer.id,
            'user_id': user.id,
            'user_name': 'alice',
            'public_key': 'alice-public',
            'allowed_ip': '10.8.0.2',
            'psk_key': 'peer-psk',
            'status': 'pending',
            'is_blocked': False,
        }
    ]
    assert provision.status_code == HTTPStatus.OK
    assert provision.json()['interface']['listen_port'] == 51820
    assert all_nodes.json()['nodes'][0]['id'] == node.id


async def test_node_results_update_only_allowed_state(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, _, peer = seeded_worker_state

    sync = await client.post(
        f'/internal/worker/nodes/{node.id}/sync-result',
        json={
            'ok': True,
            'interface': {'public_key': 'new-public', 'listen_port': 51821},
            'peers': [
                {
                    'public_key': 'alice-public',
                    'status': 'active',
                    'rx_bytes': 100,
                    'tx_bytes': 50,
                }
            ],
        },
        headers=worker_headers,
    )
    assert sync.status_code == HTTPStatus.OK
    assert sync.json() == {'status': 'ok'}

    saved_node = await db.get(Node, node.id)
    await db.refresh(saved_node)
    assert saved_node.server_public_key == 'new-public'
    assert saved_node.listen_port == 51821
    assert saved_node.health_status == 'online'

    provision_ok = await client.post(
        f'/internal/worker/nodes/{node.id}/provision-result',
        json={'ok': True, 'interface': {'listen_port': 51822}},
        headers=worker_headers,
    )

    assert provision_ok.status_code == HTTPStatus.OK
    assert provision_ok.json() == {'status': 'succeeded'}

    saved_node = await db.get(Node, node.id)
    await db.refresh(saved_node)
    assert saved_node.health_status == 'online'
    assert saved_node.provision_status == 'succeeded'

    provision = await client.post(
        f'/internal/worker/nodes/{node.id}/provision-result',
        json={'ok': False, 'error': 'boom'},
        headers=worker_headers,
    )

    assert provision.status_code == HTTPStatus.OK
    assert provision.json() == {'status': 'failed'}

    saved_node = await db.get(Node, node.id)
    saved_peer = await db.get(Peer, peer.id)
    await db.refresh(saved_node)
    await db.refresh(saved_peer)
    samples = (await db.execute(select(PeerTrafficSample))).scalars().all()
    assert saved_node.provision_status == 'failed'
    assert saved_node.last_error == 'boom'
    assert saved_peer.status == 'active'
    assert saved_peer.raw_rx == 100
    assert saved_peer.raw_tx == 50
    assert samples == []


async def test_node_results_set_health_status_on_failure(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, _, _ = seeded_worker_state

    sync = await client.post(
        f'/internal/worker/nodes/{node.id}/sync-result',
        json={'ok': False, 'error': 'sync failed'},
        headers=worker_headers,
    )

    saved_node = await db.get(Node, node.id)
    await db.refresh(saved_node)
    assert saved_node.health_status == 'offline'

    saved_node.health_status = 'online'
    await db.commit()

    provision = await client.post(
        f'/internal/worker/nodes/{node.id}/provision-result',
        json={'ok': False, 'error': 'provision failed'},
        headers=worker_headers,
    )

    assert sync.status_code == HTTPStatus.OK
    assert sync.json() == {'status': 'failed'}
    assert provision.status_code == HTTPStatus.OK
    assert provision.json() == {'status': 'failed'}

    saved_node = await db.get(Node, node.id)
    await db.refresh(saved_node)
    assert saved_node.health_status == 'offline'
    assert saved_node.last_error == 'provision failed'
