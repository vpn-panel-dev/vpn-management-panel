from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy import select

from app.models import (
    AsyncOperation,
    LocalAmneziawgTrafficDelta,
    LocalAmneziawgTrafficSettings,
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Node,
    Peer,
    PeerTrafficSample,
    RemnawaveUser,
    User,
)


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


async def test_node_sync_accounts_local_traffic_counter_increase(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    peer.raw_rx = 1_000
    peer.raw_tx = 2_000
    await db.commit()

    sync = await _post_sync_result(
        client,
        worker_headers,
        node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 1_500, 'tx_bytes': 2_600}],
    )

    assert sync.status_code == HTTPStatus.OK
    delta = await db.scalar(select(LocalAmneziawgTrafficDelta))
    user_daily = await db.scalar(select(LocalAmneziawgUserDailyTraffic))
    user_node_daily = await db.scalar(select(LocalAmneziawgUserNodeDailyTraffic))
    user_lifetime = await db.scalar(select(LocalAmneziawgUserLifetimeTraffic))
    user_node_lifetime = await db.scalar(select(LocalAmneziawgUserNodeLifetimeTraffic))
    sample = await db.scalar(select(PeerTrafficSample))

    assert delta is not None
    assert delta.peer_id == peer.id
    assert delta.node_id == node.id
    assert delta.user_id == user.id
    assert delta.previous_rx_bytes == 1_000
    assert delta.previous_tx_bytes == 2_000
    assert delta.current_rx_bytes == 1_500
    assert delta.current_tx_bytes == 2_600
    assert delta.rx_delta_bytes == 500
    assert delta.tx_delta_bytes == 600
    assert delta.total_delta_bytes == 1_100
    assert delta.rx_reset_detected is False
    assert delta.tx_reset_detected is False
    assert sample is not None
    assert (sample.rx_bytes, sample.tx_bytes) == (500, 600)
    assert user_daily is not None
    assert (user_daily.rx_bytes, user_daily.tx_bytes, user_daily.total_bytes) == (500, 600, 1_100)
    assert user_node_daily is not None
    assert user_node_daily.node_id == node.id
    assert (user_node_daily.rx_bytes, user_node_daily.tx_bytes, user_node_daily.total_bytes) == (
        500,
        600,
        1_100,
    )
    assert user_lifetime is not None
    assert (user_lifetime.rx_bytes, user_lifetime.tx_bytes, user_lifetime.total_bytes) == (
        500,
        600,
        1_100,
    )
    assert user_node_lifetime is not None
    assert user_node_lifetime.node_id == node.id
    assert (
        user_node_lifetime.rx_bytes,
        user_node_lifetime.tx_bytes,
        user_node_lifetime.total_bytes,
    ) == (500, 600, 1_100)


async def test_node_sync_accounts_counter_reset_as_post_reset_usage(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    peer.raw_rx = 5_000
    peer.raw_tx = 5_000
    await db.commit()

    sync = await _post_sync_result(
        client,
        worker_headers,
        node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 100, 'tx_bytes': 200}],
    )

    assert sync.status_code == HTTPStatus.OK
    delta = await db.scalar(select(LocalAmneziawgTrafficDelta))
    user_lifetime = await db.scalar(select(LocalAmneziawgUserLifetimeTraffic))

    assert delta is not None
    assert delta.previous_rx_bytes == 5_000
    assert delta.previous_tx_bytes == 5_000
    assert delta.rx_delta_bytes == 100
    assert delta.tx_delta_bytes == 200
    assert delta.total_delta_bytes == 300
    assert delta.rx_reset_detected is True
    assert delta.tx_reset_detected is True
    assert user_lifetime is not None
    assert user_lifetime.total_bytes == 300


async def test_node_sync_duplicate_counters_do_not_increment_local_usage(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    peer.raw_rx = 100
    peer.raw_tx = 200
    await db.commit()

    first = await _post_sync_result(
        client,
        worker_headers,
        node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 150, 'tx_bytes': 250}],
    )
    duplicate = await _post_sync_result(
        client,
        worker_headers,
        node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 150, 'tx_bytes': 250}],
    )

    assert first.status_code == HTTPStatus.OK
    assert duplicate.status_code == HTTPStatus.OK
    deltas = (await db.execute(select(LocalAmneziawgTrafficDelta))).scalars().all()
    user_lifetime = await db.scalar(select(LocalAmneziawgUserLifetimeTraffic))

    assert len(deltas) == 1
    assert deltas[0].total_delta_bytes == 100
    assert user_lifetime is not None
    assert user_lifetime.total_bytes == 100


async def test_node_sync_missing_bytes_skips_local_accounting(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    peer.raw_rx = 100
    peer.raw_tx = 200
    await db.commit()

    sync = await _post_sync_result(
        client,
        worker_headers,
        node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 150}],
    )

    saved_peer = await db.get(Peer, peer.id)
    deltas = (await db.execute(select(LocalAmneziawgTrafficDelta))).scalars().all()
    samples = (await db.execute(select(PeerTrafficSample))).scalars().all()

    assert sync.status_code == HTTPStatus.OK
    assert saved_peer is not None
    await db.refresh(saved_peer)
    assert saved_peer.status == 'active'
    assert saved_peer.raw_rx == 100
    assert saved_peer.raw_tx == 200
    assert deltas == []
    assert samples == []


async def test_node_sync_local_accounting_sums_multi_node_user_totals(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    second_node = Node(
        id='node-2',
        name='node-2',
        url='http://agent-2:8000',
        token='node-token-2',  # noqa: S106
    )
    second_peer = Peer(id='peer-2', node=second_node, user=user, status='active')
    peer.raw_rx = 1_000
    peer.raw_tx = 2_000
    second_peer.raw_rx = 10
    second_peer.raw_tx = 20
    db.add_all([second_node, second_peer])
    await db.commit()

    first_sync = await _post_sync_result(
        client,
        worker_headers,
        node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 1_500, 'tx_bytes': 2_600}],
    )
    second_sync = await _post_sync_result(
        client,
        worker_headers,
        second_node.id,
        [{'public_key': user.public_key, 'status': 'active', 'rx_bytes': 20, 'tx_bytes': 45}],
    )

    assert first_sync.status_code == HTTPStatus.OK
    assert second_sync.status_code == HTTPStatus.OK
    user_lifetime = await db.scalar(select(LocalAmneziawgUserLifetimeTraffic))
    node_lifetimes = (
        (await db.execute(select(LocalAmneziawgUserNodeLifetimeTraffic))).scalars().all()
    )
    totals_by_node = {row.node_id: row.total_bytes for row in node_lifetimes}

    assert user_lifetime is not None
    assert user_lifetime.total_bytes == 1_135
    assert totals_by_node == {'node-1': 1_100, 'node-2': 35}


async def test_node_sync_blocks_remnawave_user_when_combined_usage_reaches_limit(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    user_id = user.id
    peer_id = peer.id
    peer.raw_rx = 1_000
    peer.raw_tx = 2_000
    db.add(
        RemnawaveUser(
            user_id=user.id,
            remnawave_uuid='rw-limited-by-local',
            username='alice',
            status='ACTIVE',
            traffic_used_bytes=800,
            traffic_limit_bytes=1_000,
        )
    )
    await db.commit()

    with (
        patch('app.routers.internal_worker.enqueue_sync_node', new=AsyncMock()) as enqueue_sync,
        patch(
            'app.routers.internal_worker.enqueue_remnawave_disable_user', new=AsyncMock()
        ) as enqueue_disable,
    ):
        sync = await _post_sync_result(
            client,
            worker_headers,
            node.id,
            [
                {
                    'public_key': user.public_key,
                    'status': 'active',
                    'rx_bytes': 1_100,
                    'tx_bytes': 2_250,
                }
            ],
        )

    assert sync.status_code == HTTPStatus.OK
    db.expire_all()
    updated_user = await db.get(User, user_id)
    updated_peer = await db.get(Peer, peer_id)
    user_lifetime = await db.scalar(select(LocalAmneziawgUserLifetimeTraffic))
    assert user_lifetime is not None
    assert user_lifetime.total_bytes == 350
    assert updated_user.is_blocked is True
    assert updated_peer.status == 'pending_delete'
    enqueue_sync.assert_awaited_once()
    enqueue_disable.assert_awaited_once()


async def test_worker_raw_sample_cleanup_deletes_only_persisted_old_samples(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    old = datetime.now(UTC) - timedelta(days=100)
    recent = datetime.now(UTC) - timedelta(days=10)
    persisted_old_sample = PeerTrafficSample(
        id='old-persisted-sample',
        peer_id=peer.id,
        sampled_at=old,
        rx_bytes=100,
        tx_bytes=200,
    )
    unpersisted_old_sample = PeerTrafficSample(
        id='old-unpersisted-sample',
        peer_id=peer.id,
        sampled_at=old + timedelta(minutes=1),
        rx_bytes=10,
        tx_bytes=20,
    )
    recent_sample = PeerTrafficSample(
        id='recent-sample',
        peer_id=peer.id,
        sampled_at=recent,
        rx_bytes=30,
        tx_bytes=40,
    )
    delta = LocalAmneziawgTrafficDelta(
        id='delta-1',
        peer_id=peer.id,
        node_id=node.id,
        user_id=user.id,
        observed_at=old,
        previous_rx_bytes=1_000,
        previous_tx_bytes=2_000,
        current_rx_bytes=1_100,
        current_tx_bytes=2_200,
        rx_delta_bytes=100,
        tx_delta_bytes=200,
        total_delta_bytes=300,
    )
    user_daily = LocalAmneziawgUserDailyTraffic(
        user_id=user.id,
        day=old.date(),
        rx_bytes=100,
        tx_bytes=200,
        total_bytes=300,
    )
    user_node_daily = LocalAmneziawgUserNodeDailyTraffic(
        user_id=user.id,
        node_id=node.id,
        day=old.date(),
        rx_bytes=100,
        tx_bytes=200,
        total_bytes=300,
    )
    user_lifetime = LocalAmneziawgUserLifetimeTraffic(
        user_id=user.id,
        rx_bytes=100,
        tx_bytes=200,
        total_bytes=300,
    )
    user_node_lifetime = LocalAmneziawgUserNodeLifetimeTraffic(
        user_id=user.id,
        node_id=node.id,
        rx_bytes=100,
        tx_bytes=200,
        total_bytes=300,
    )
    db.add_all(
        [
            persisted_old_sample,
            unpersisted_old_sample,
            recent_sample,
            delta,
            user_daily,
            user_node_daily,
            user_lifetime,
            user_node_lifetime,
        ]
    )
    await db.commit()

    cleanup = await client.post(
        '/internal/worker/traffic/cleanup-raw-samples', headers=worker_headers
    )

    remaining_samples = (await db.execute(select(PeerTrafficSample))).scalars().all()
    remaining_deltas = (await db.execute(select(LocalAmneziawgTrafficDelta))).scalars().all()
    await db.refresh(user_daily)
    await db.refresh(user_node_daily)
    await db.refresh(user_lifetime)
    await db.refresh(user_node_lifetime)

    assert cleanup.status_code == HTTPStatus.OK
    assert cleanup.json()['retention_days'] == 90
    assert cleanup.json()['deleted'] == 1
    assert cleanup.json()['disabled'] is False
    assert {sample.id for sample in remaining_samples} == {
        'old-unpersisted-sample',
        'recent-sample',
    }
    assert [row.id for row in remaining_deltas] == ['delta-1']
    assert (user_daily.rx_bytes, user_daily.tx_bytes, user_daily.total_bytes) == (100, 200, 300)
    assert (user_node_daily.rx_bytes, user_node_daily.tx_bytes, user_node_daily.total_bytes) == (
        100,
        200,
        300,
    )
    assert (user_lifetime.rx_bytes, user_lifetime.tx_bytes, user_lifetime.total_bytes) == (
        100,
        200,
        300,
    )
    assert (
        user_node_lifetime.rx_bytes,
        user_node_lifetime.tx_bytes,
        user_node_lifetime.total_bytes,
    ) == (100, 200, 300)


async def test_worker_raw_sample_cleanup_is_disabled_when_retention_is_zero(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    _, _, peer = seeded_worker_state
    old = datetime.now(UTC) - timedelta(days=100)
    settings = await LocalAmneziawgTrafficSettings.get_settings(db)
    settings.raw_sample_retention_days = 0
    db.add(PeerTrafficSample(peer_id=peer.id, sampled_at=old, rx_bytes=100, tx_bytes=200))
    await db.commit()

    cleanup = await client.post(
        '/internal/worker/traffic/cleanup-raw-samples', headers=worker_headers
    )

    samples = (await db.execute(select(PeerTrafficSample))).scalars().all()
    assert cleanup.status_code == HTTPStatus.OK
    assert cleanup.json() == {
        'status': 'ok',
        'retention_days': 0,
        'deleted': 0,
        'disabled': True,
        'cutoff': None,
    }
    assert len(samples) == 1


async def test_node_sync_keeps_pending_delete_and_blocked_user_behavior(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, user, peer = seeded_worker_state
    user.is_blocked = True
    peer.status = 'pending_delete'
    await db.commit()

    sync = await _post_sync_result(client, worker_headers, node.id, [])

    saved_user = await db.get(User, user.id)
    saved_peer = await db.get(Peer, peer.id)

    assert sync.status_code == HTTPStatus.OK
    assert saved_user is not None
    await db.refresh(saved_user)
    assert saved_user.is_blocked is True
    assert saved_peer is not None
    await db.refresh(saved_peer)
    assert saved_peer.status == 'deleted'


async def test_remnawave_reconcile_complete_marks_missing_users_and_is_idempotent(
    client: AsyncClient, db, worker_headers, seeded_worker_state
):
    node, _, _ = seeded_worker_state
    seen_user = User(name='seen-user')
    missing_user = User(name='missing-user')
    missing_peer = Peer(node_id=node.id, user=missing_user, status='pending')
    db.add_all(
        [
            seen_user,
            missing_user,
            missing_peer,
            RemnawaveUser(
                user=seen_user,
                remnawave_uuid='seen-uuid',
                username='seen',
                status='ACTIVE',
            ),
            RemnawaveUser(
                user=missing_user,
                remnawave_uuid='missing-uuid',
                username='missing',
                status='ACTIVE',
            ),
        ]
    )
    await db.flush()
    missing_peer_id = missing_peer.id
    await db.commit()

    with patch('app.routers.internal_worker.enqueue_sync_node', new=AsyncMock()) as enqueue:
        resp = await client.post(
            '/internal/worker/remnawave/reconcile-complete',
            json={'seen_uuids': ['seen-uuid']},
            headers=worker_headers,
        )
        repeat = await client.post(
            '/internal/worker/remnawave/reconcile-complete',
            json={'seen_uuids': ['seen-uuid']},
            headers=worker_headers,
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'status': 'ok',
        'purged': 0,
        'affected_node_ids': ['node-1'],
    }
    assert repeat.status_code == HTTPStatus.OK
    assert repeat.json() == {
        'status': 'ok',
        'purged': 0,
        'affected_node_ids': [],
    }
    assert enqueue.await_count == 1

    result = await db.execute(
        select(
            RemnawaveUser.sync_status,
            RemnawaveUser.sync_reason,
            User.is_blocked,
            Peer.status,
        )
        .join(RemnawaveUser.user)
        .join(User.peers)
        .where(RemnawaveUser.remnawave_uuid == 'missing-uuid', Peer.id == missing_peer_id)
    )
    sync_status, sync_reason, is_blocked, peer_status = result.one()

    assert sync_status == 'stale'
    assert sync_reason == 'remote user missing'
    assert is_blocked is True
    assert peer_status == 'pending_delete'


async def _post_sync_result(
    client: AsyncClient,
    worker_headers: dict[str, str],
    node_id: str,
    peers: list[dict],
):
    return await client.post(
        f'/internal/worker/nodes/{node_id}/sync-result',
        json={'ok': True, 'peers': peers},
        headers=worker_headers,
    )
