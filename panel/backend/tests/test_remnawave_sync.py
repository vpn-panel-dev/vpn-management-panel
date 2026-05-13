from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Peer, RemnawaveUser, User

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
    client: AsyncClient, auth_headers, worker_headers, seeded_node
):
    assert seeded_node.id == 'node-1'
    profile = _profile(
        email='alice@example.com',
        tag='premium',
    )
    profile['traffic_used_bytes'] = 1_000_000
    profile['traffic_limit_bytes'] = 10_000_000
    await client.post(
        '/internal/worker/remnawave/users/upsert', json=[profile], headers=worker_headers
    )

    headers = auth_headers
    resp = await client.get('/api/users', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    users = resp.json()
    rw_user = next(u for u in users if u['remnawave'] is not None)

    brief = rw_user['remnawave']
    assert brief['email'] == 'alice@example.com'
    assert brief['tag'] == 'premium'
    assert brief['traffic_used_bytes'] == 1_000_000
    assert brief['traffic_limit_bytes'] == 10_000_000
    assert brief['delete_requested_at'] is None
