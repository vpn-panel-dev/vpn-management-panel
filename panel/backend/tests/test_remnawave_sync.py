from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import BigInteger, select

from app.models import LocalAmneziawgUserLifetimeTraffic, Peer, RemnawaveUser, User
from app.routers.api_parts.common import REMNAWAVE_MANAGED_USER_CONFLICT_DETAIL
from app.services.remnawave_sync import reconcile_missing_remnawave_users

pytestmark = pytest.mark.usefixtures('mock_sync_node_enqueue')


def _profile(**overrides):
    data = {
        'uuid': 'rw-uuid-1',
        'short_uuid': 'abc123',
        'username': 'alice',
        'status': 'ACTIVE',
        'expire_at': (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    }
    data.update(overrides)
    return data


async def test_upsert_active_import_creates_user_peer_and_mapping(
    client: AsyncClient, db, worker_headers, seeded_node
):
    node = seeded_node

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['affected_node_ids'] == [node.id]
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    user = await db.get(User, rw_user.user_id)
    peers = (await db.execute(select(Peer).where(Peer.user_id == user.id))).scalars().all()
    assert user.name == 'alice'
    assert user.is_blocked is False
    assert user.public_key
    assert user.private_key
    assert user.vpn_ip == '10.8.0.2'
    assert len(peers) == 1
    assert peers[0].status == 'pending'
    assert rw_user.sync_status == 'synced'
    assert rw_user.sync_reason is None
    assert rw_user.sync_error is None


async def test_upsert_accepts_worker_normalized_remnawave_uuid(
    client: AsyncClient, db, worker_headers, seeded_node
):
    _ = seeded_node
    profile = _profile(username='worker-alice', active_internal_squads=['squad-a'])
    profile.pop('uuid')
    profile['remnawave_uuid'] = 'worker-rw-uuid'
    profile['remnawave_id'] = 42

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[profile],
        headers=worker_headers,
    )

    assert resp.status_code == HTTPStatus.OK
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    assert rw_user.remnawave_uuid == 'worker-rw-uuid'
    assert rw_user.remnawave_id == 42
    assert rw_user.active_internal_squads_json == '["squad-a"]'


async def test_upsert_disabled_and_expired_profiles_are_blocked(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    expired = datetime.now(UTC) - timedelta(minutes=1)

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[
            _profile(uuid='disabled-uuid', username='disabled', status='DISABLED'),
            _profile(
                uuid='expired-uuid',
                username='expired',
                status='ACTIVE',
                expire_at=expired.isoformat(),
            ),
        ],
        headers=worker_headers,
    )

    assert resp.status_code == HTTPStatus.OK
    users = (await db.execute(select(User).order_by(User.name))).scalars().all()
    assert {user.name: user.is_blocked for user in users} == {'disabled': True, 'expired': True}


async def test_upsert_active_profiles_overwrite_local_block_state(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    user_id = rw_user.user_id
    user = await db.get(User, rw_user.user_id)
    peer = (await db.execute(select(Peer).where(Peer.user_id == user_id))).scalar_one()

    user.is_blocked = True
    peer.status = 'pending_delete'
    await db.commit()

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )

    assert resp.status_code == HTTPStatus.OK
    db.expire_all()
    updated_rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    updated_user = await db.get(User, user_id)
    updated_peer = (await db.execute(select(Peer).where(Peer.user_id == user_id))).scalar_one()
    assert updated_user.is_blocked is False
    assert updated_peer.status == 'pending'
    assert updated_rw_user.sync_status == 'synced'


async def test_upsert_blocks_when_combined_usage_reaches_remnawave_limit(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=rw_user.user_id,
            rx_bytes=100,
            tx_bytes=250,
            total_bytes=350,
        )
    )
    await db.commit()

    profile = _profile(traffic_used_bytes=800, traffic_limit_bytes=1_000)
    with patch(
        'app.routers.internal_worker.enqueue_remnawave_disable_user', new=AsyncMock()
    ) as enqueue:
        resp = await client.post(
            '/internal/worker/remnawave/users/upsert', json=[profile], headers=worker_headers
        )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['affected_node_ids'] == ['node-1']
    assert resp.json()['remote_disable_uuids'] == ['rw-uuid-1']
    db.expire_all()
    updated_rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    updated_user = await db.get(User, updated_rw_user.user_id)
    peer = (await db.execute(select(Peer).where(Peer.user_id == updated_user.id))).scalar_one()
    assert updated_user.is_blocked is True
    assert peer.status == 'pending_delete'
    enqueue.assert_awaited_once()


async def test_upsert_accepts_remnawave_traffic_values_above_postgres_integer_limit(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    profile = _profile(
        traffic_limit_bytes=50 * 1024**3,
        traffic_used_bytes=25 * 1024**3,
        lifetime_used_traffic_bytes=25 * 1024**3,
    )

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert', json=[profile], headers=worker_headers
    )

    assert resp.status_code == HTTPStatus.OK
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    assert rw_user.traffic_limit_bytes == 50 * 1024**3
    assert rw_user.traffic_used_bytes == 25 * 1024**3
    assert rw_user.lifetime_used_traffic_bytes == 25 * 1024**3
    assert isinstance(RemnawaveUser.traffic_limit_bytes.type, BigInteger)
    assert isinstance(RemnawaveUser.traffic_used_bytes.type, BigInteger)
    assert isinstance(RemnawaveUser.lifetime_used_traffic_bytes.type, BigInteger)


async def test_upsert_accepts_telegram_id_above_postgres_integer_limit(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    profile = _profile(telegram_id=5_149_087_582)

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert', json=[profile], headers=worker_headers
    )

    assert resp.status_code == HTTPStatus.OK
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    assert rw_user.telegram_id == 5_149_087_582
    assert isinstance(RemnawaveUser.telegram_id.type, BigInteger)


async def test_upsert_failure_returns_readable_worker_detail(
    client: AsyncClient, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'

    with patch(
        'app.routers.internal_worker_parts.remnawave.create_remnawave_local_user',
        new=AsyncMock(side_effect=RuntimeError('integer out of range')),
    ):
        resp = await client.post(
            '/internal/worker/remnawave/users/upsert',
            json=[_profile()],
            headers=worker_headers,
        )

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert resp.json() == {
        'detail': 'Remnawave users upsert failed: integer out of range',
    }


async def test_upsert_never_auto_links_by_username_and_suffixes_conflict(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    db.add(User(name='alice'))
    await db.commit()

    resp = await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )

    assert resp.status_code == HTTPStatus.OK
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    linked_user = await db.get(User, rw_user.user_id)
    local_alice = (await db.execute(select(User).where(User.name == 'alice'))).scalar_one()
    assert linked_user.id != local_alice.id
    assert linked_user.name == 'alice__rw_abc123'


async def test_remote_delete_waits_for_peer_removal_before_purge(
    client: AsyncClient, db, worker_headers, seeded_node
):
    node = seeded_node
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    user_id = rw_user.user_id

    deleted = await client.post(
        f'/internal/worker/remnawave/users/{rw_user.remnawave_uuid}/deleted', headers=worker_headers
    )
    still_present = await db.get(User, user_id)
    peer = (await db.execute(select(Peer).where(Peer.user_id == user_id))).scalar_one()

    assert deleted.status_code == HTTPStatus.OK
    assert still_present is not None
    assert still_present.is_blocked is True
    assert peer.status == 'pending_delete'

    sync = await client.post(
        f'/internal/worker/nodes/{node.id}/sync-result',
        json={'ok': True, 'peers': []},
        headers=worker_headers,
    )

    assert sync.status_code == HTTPStatus.OK
    db.expire_all()
    assert await db.get(User, user_id) is None
    assert (await db.execute(select(RemnawaveUser))).scalar_one_or_none() is None


async def test_missing_remote_users_become_stale_without_delete(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert',
        json=[_profile(uuid='missing-uuid', username='missing'), _profile()],
        headers=worker_headers,
    )
    remote_uuid = (
        (await db.execute(select(RemnawaveUser).where(RemnawaveUser.username == 'alice')))
        .scalar_one()
        .remnawave_uuid
    )
    affected_nodes = await reconcile_missing_remnawave_users(db, {remote_uuid})
    assert affected_nodes == {'node-1'}
    await db.commit()

    stale_row = (
        await db.execute(select(RemnawaveUser).where(RemnawaveUser.username == 'missing'))
    ).scalar_one()
    stale_user = await db.get(User, stale_row.user_id)
    stale_peer = (await db.execute(select(Peer).where(Peer.user_id == stale_user.id))).scalar_one()
    assert stale_row.sync_status == 'stale'
    assert stale_row.sync_reason == 'remote user missing'
    assert stale_user is not None
    assert stale_user.is_blocked is True
    assert stale_peer.status == 'pending_delete'


async def test_local_block_unblock_delete_reject_remnawave_managed_user(
    client: AsyncClient, db, auth_headers, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    headers = auth_headers

    block = await client.put(f'/api/users/{rw_user.user_id}/block', headers=headers)
    unblock = await client.put(f'/api/users/{rw_user.user_id}/unblock', headers=headers)
    delete = await client.delete(f'/api/users/{rw_user.user_id}', headers=headers)

    assert block.status_code == HTTPStatus.CONFLICT
    assert unblock.status_code == HTTPStatus.CONFLICT
    assert delete.status_code == HTTPStatus.CONFLICT
    assert block.json()['detail'] == REMNAWAVE_MANAGED_USER_CONFLICT_DETAIL
    assert unblock.json()['detail'] == REMNAWAVE_MANAGED_USER_CONFLICT_DETAIL
    assert delete.json()['detail'] == REMNAWAVE_MANAGED_USER_CONFLICT_DETAIL


async def test_standalone_local_users_remain_editable(client: AsyncClient, auth_headers):
    created = await client.post('/api/users', json={'name': 'local-only'}, headers=auth_headers)
    assert created.status_code == HTTPStatus.CREATED
    user_id = created.json()['id']

    block = await client.put(f'/api/users/{user_id}/block', headers=auth_headers)
    unblock = await client.put(f'/api/users/{user_id}/unblock', headers=auth_headers)
    delete = await client.delete(f'/api/users/{user_id}', headers=auth_headers)

    assert block.status_code == HTTPStatus.OK
    assert unblock.status_code == HTTPStatus.OK
    assert delete.status_code == HTTPStatus.NO_CONTENT


async def test_user_list_includes_remnawave_summary_for_linked_users(
    client: AsyncClient, db, auth_headers, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    # Also create a plain local user
    db.add(User(name='local-only'))
    await db.commit()

    headers = auth_headers
    resp = await client.get('/api/users', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()

    rw_linked = next(u for u in users if u['name'] != 'local-only')
    local_user = next(u for u in users if u['name'] == 'local-only')

    assert rw_linked['remnawave'] is not None
    assert rw_linked['remnawave']['uuid'] == 'rw-uuid-1'
    assert rw_linked['remnawave']['username'] == 'alice'
    assert rw_linked['remnawave']['status'] == 'ACTIVE'
    assert local_user['remnawave'] is None


async def test_user_list_remnawave_brief_fields(
    client: AsyncClient, db, auth_headers, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    profile = _profile(
        email='alice@example.com',
        tag='premium',
        description='Bot user: Alice Example @alice_example',
        telegram_id=5_149_087_582,
    )
    profile['traffic_used_bytes'] = 1_000_000
    profile['traffic_limit_bytes'] = 10_000_000
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[profile], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=rw_user.user_id,
            rx_bytes=100,
            tx_bytes=250,
            total_bytes=350,
        )
    )
    await db.commit()

    headers = auth_headers
    resp = await client.get('/api/users', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()
    rw_user = next(u for u in users if u['remnawave'] is not None)

    brief = rw_user['remnawave']
    assert brief['email'] == 'alice@example.com'
    assert brief['tag'] == 'premium'
    assert brief['display_name'] == 'Alice Example'
    assert brief['telegram_username'] == 'alice_example'
    assert brief['telegram_url'] == 'https://t.me/alice_example'
    assert brief['description'] == 'Bot user: Alice Example @alice_example'
    assert brief['telegram_id'] == 5_149_087_582
    assert brief['traffic_used_bytes'] == 1_000_000
    assert brief['traffic_limit_bytes'] == 10_000_000
    assert brief['local_amneziawg_traffic_used_bytes'] == 350
    assert brief['combined_traffic_used_bytes'] == 1_000_350
    assert brief['blocked_reason'] is None
    assert brief['delete_requested_at'] is None
    assert 'remnawave_url' not in brief
    assert 'remnawave_link' not in brief


async def test_user_list_remnawave_display_fields_fallback_when_description_malformed(
    client: AsyncClient, auth_headers, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    profile = _profile(
        uuid='telegram-id-only-uuid',
        username='telegram-id-only',
        description='External text with https://evil.example/@not_a_bot_user',
        telegram_id=4_242_424_242,
    )
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[profile], headers=worker_headers
    )

    resp = await client.get('/api/users', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()
    brief = next(u['remnawave'] for u in users if u['remnawave'] is not None)

    assert brief['display_name'] is None
    assert brief['telegram_username'] is None
    assert brief['telegram_url'] == 'tg://user?id=4242424242'
    assert brief['description'] == 'External text with https://evil.example/@not_a_bot_user'
    assert brief['telegram_id'] == 4_242_424_242
    assert 'remnawave_url' not in brief
    assert 'remnawave_link' not in brief


async def test_user_list_includes_remnawave_sync_metadata(
    client: AsyncClient, db, auth_headers, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()
    rw_user.sync_status = 'stale'
    rw_user.sync_reason = 'remote snapshot is older than local state'
    rw_user.sync_error = 'timeout while syncing'
    rw_user.last_synced_at = datetime(2026, 1, 1, tzinfo=UTC)
    await db.commit()

    resp = await client.get('/api/users', headers=auth_headers)
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()
    brief = next(u['remnawave'] for u in users if u['remnawave'] is not None)

    assert brief['sync_status'] == 'stale'
    assert brief['sync_reason'] == 'remote snapshot is older than local state'
    assert brief['sync_error'] == 'timeout while syncing'
    assert brief['last_synced_at'] == '2026-01-01T00:00:00'
    assert brief['blocked_reason'] == 'deleted'


async def test_delete_request_marks_user_missing_in_sync_metadata(
    client: AsyncClient, db, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[_profile()], headers=worker_headers
    )
    rw_user = (await db.execute(select(RemnawaveUser))).scalar_one()

    resp = await client.post(
        f'/internal/worker/remnawave/users/{rw_user.remnawave_uuid}/deleted',
        headers=worker_headers,
    )

    assert resp.status_code == HTTPStatus.OK
    db.expire_all()
    updated = (await db.execute(select(RemnawaveUser))).scalar_one()
    assert updated.sync_status == 'missing'
    assert updated.sync_reason == 'delete requested'
