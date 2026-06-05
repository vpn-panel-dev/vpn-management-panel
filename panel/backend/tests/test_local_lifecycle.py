"""Tests for P4 standalone lifecycle v1.

Covers:
- ``app.services.local_lifecycle`` helpers and state enforcement
- ``PUT /api/users/{id}/lifecycle`` admin endpoint
- ``POST /api/users/{id}/lifecycle/reset-traffic`` admin endpoint
- ``POST /api/users/{id}/public-link/regenerate`` admin endpoint
- ``PUT /api/users/{id}/unblock`` 409 when lifecycle blocks the user
- Public ``/pub/u/{token_or_id}/*`` access via ``public_token``
- Public status/traffic mapping for local users (expired/limited/active)
- Remnawave-managed users are protected from local lifecycle writes
- Local lifecycle enforcement inside ``node_sync_result`` worker handler
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Node,
    Peer,
    RemnawaveUser,
    User,
)
from app.services.local_lifecycle import (
    apply_local_lifecycle_state,
    aware,
    enforce_local_lifecycle_for_user,
    load_local_total_bytes,
    load_local_user,
    local_user_blocked_reason,
    local_user_expired,
    local_user_limited,
    now,
    reset_local_traffic_usage,
)

# ── Service-layer unit tests ───────────────────────────────────────────────────


def _make_user(**overrides: Any) -> User:
    defaults: dict[str, Any] = {
        'id': 'u-1',
        'name': 'local-user',
        'public_key': 'pk',
        'private_key': 'sk',
        'vpn_ip': '10.8.0.2',
        'public_token': secrets.token_urlsafe(24),
        'is_blocked': False,
        'lifecycle_status': 'active',
        'expire_at': None,
        'traffic_limit_bytes': 0,
        'traffic_reset_policy': 'manual',
        'traffic_reset_at': None,
    }
    defaults.update(overrides)
    return User(**defaults)


def test_aware_makes_naive_datetime_utc() -> None:
    naive = datetime(2026, 6, 1, 12, 0, 0)
    assert naive.tzinfo is None
    result = aware(naive)
    assert result is not None
    assert result.tzinfo is UTC


def test_aware_preserves_aware_datetime() -> None:
    aware_dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    assert aware(aware_dt) is aware_dt


def test_aware_passes_through_none() -> None:
    assert aware(None) is None


def test_now_returns_aware_utc() -> None:
    assert now().tzinfo is UTC


def test_local_user_expired_false_when_no_expire_at() -> None:
    assert local_user_expired(_make_user(expire_at=None)) is False


def test_local_user_expired_true_when_expire_at_in_past() -> None:
    past = datetime(2026, 1, 1, tzinfo=UTC)
    assert local_user_expired(_make_user(expire_at=past)) is True


def test_local_user_expired_false_when_expire_at_in_future() -> None:
    future = now() + timedelta(days=1)
    assert local_user_expired(_make_user(expire_at=future)) is False


def test_local_user_expired_uses_observed_at() -> None:
    expire = datetime(2026, 1, 1, tzinfo=UTC)
    before = datetime(2025, 12, 1, tzinfo=UTC)
    after = datetime(2026, 2, 1, tzinfo=UTC)
    assert local_user_expired(_make_user(expire_at=expire), observed_at=before) is False
    assert local_user_expired(_make_user(expire_at=expire), observed_at=after) is True


def test_local_user_limited_false_when_limit_zero() -> None:
    user = _make_user(traffic_limit_bytes=0)
    assert local_user_limited(user, local_total_bytes=1_000) is False


def test_local_user_limited_false_when_under_limit() -> None:
    user = _make_user(traffic_limit_bytes=1_000)
    assert local_user_limited(user, local_total_bytes=500) is False


def test_local_user_limited_true_when_at_or_over_limit() -> None:
    user = _make_user(traffic_limit_bytes=1_000)
    assert local_user_limited(user, local_total_bytes=1_000) is True
    assert local_user_limited(user, local_total_bytes=2_000) is True


def test_local_user_blocked_reason_expired_takes_precedence_over_limited() -> None:
    user = _make_user(
        expire_at=datetime(2020, 1, 1, tzinfo=UTC),
        traffic_limit_bytes=1_000,
    )
    assert local_user_blocked_reason(user, local_total_bytes=2_000) == 'expired'


def test_local_user_blocked_reason_limited_when_under_limit_and_no_expiry() -> None:
    user = _make_user(traffic_limit_bytes=1_000)
    assert local_user_blocked_reason(user, local_total_bytes=2_000) == 'limited'


def test_local_user_blocked_reason_blocked_from_lifecycle_status() -> None:
    user = _make_user(
        lifecycle_status='blocked',
        is_blocked=True,
    )
    assert local_user_blocked_reason(user, local_total_bytes=0) == 'blocked'


def test_local_user_blocked_reason_none_when_active() -> None:
    assert local_user_blocked_reason(_make_user(), local_total_bytes=0) is None


async def test_load_local_user_returns_none_for_missing(db: AsyncSession) -> None:
    assert await load_local_user(db, 'nope') is None


async def test_load_local_total_bytes_returns_zero_when_no_rows(
    db: AsyncSession,
) -> None:
    user = _make_user(id='u-traffic-zero')
    db.add(user)
    await db.commit()
    assert await load_local_total_bytes(db, user.id) == 0


async def test_load_local_total_bytes_sums_lifetime_row(db: AsyncSession) -> None:
    user = _make_user(id='u-traffic-sum')
    db.add(user)
    await db.flush()
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user.id,
            rx_bytes=10,
            tx_bytes=20,
            total_bytes=30,
            updated_at=now(),
        )
    )
    await db.commit()
    assert await load_local_total_bytes(db, user.id) == 30


async def _load_user_with_peers(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(
        select(User).options(selectinload(User.peers)).where(User.id == user_id)
    )
    return result.scalar_one()


async def test_apply_local_lifecycle_state_expires_and_blocks_peers(
    db: AsyncSession,
) -> None:
    node = Node(
        id='node-lc',
        name='n1',
        url='http://agent',
        token='tok',  # noqa: S106
    )
    user = _make_user(
        id='u-expire',
        expire_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    peer = Peer(
        node=node,
        user=user,
        status='pending',
        psk_key='p',
    )
    db.add_all([node, user, peer])
    await db.commit()
    user_id = user.id
    peer_id = peer.id
    node_id = node.id
    db.expire_all()

    reloaded_user = await _load_user_with_peers(db, user_id)
    affected = await apply_local_lifecycle_state(db, reloaded_user, local_total_bytes=0)
    await db.commit()
    db.expire_all()

    reloaded = await db.get(User, user_id)
    assert reloaded is not None
    reloaded_peer = await db.get(Peer, peer_id)
    assert reloaded_peer is not None
    assert reloaded.lifecycle_status == 'expired'
    assert reloaded.is_blocked is True
    assert reloaded_peer.status == 'pending_delete'
    assert node_id in affected


async def test_apply_local_lifecycle_state_limits_user_by_traffic(
    db: AsyncSession,
) -> None:
    user = _make_user(
        id='u-limit',
        traffic_limit_bytes=1_000,
    )
    db.add(user)
    await db.commit()
    user_id = user.id
    db.expire_all()

    reloaded_user = await _load_user_with_peers(db, user_id)
    affected = await apply_local_lifecycle_state(db, reloaded_user, local_total_bytes=2_000)
    await db.commit()
    db.expire_all()

    reloaded = await db.get(User, user_id)
    assert reloaded is not None
    assert reloaded.lifecycle_status == 'limited'
    assert reloaded.is_blocked is True
    assert affected == set()


async def test_apply_local_lifecycle_state_restores_pending_peers_on_recovery(
    db: AsyncSession,
) -> None:
    node = Node(
        id='node-restore',
        name='n2',
        url='http://agent',
        token='tok',  # noqa: S106
    )
    user = _make_user(id='u-restore')
    peer = Peer(
        node=node,
        user=user,
        status='pending_delete',
        psk_key='p',
    )
    db.add_all([node, user, peer])
    await db.commit()
    user_id = user.id
    peer_id = peer.id
    node_id = node.id
    db.expire_all()

    reloaded_user = await _load_user_with_peers(db, user_id)
    affected = await apply_local_lifecycle_state(db, reloaded_user, local_total_bytes=0)
    await db.commit()
    db.expire_all()

    reloaded_peer = await db.get(Peer, peer_id)
    assert reloaded_peer is not None
    assert reloaded_peer.status == 'pending'
    assert node_id in affected


async def test_apply_local_lifecycle_state_keeps_pending_delete_for_re_blocked_peer(
    db: AsyncSession,
) -> None:
    user = _make_user(
        id='u-reblock',
        expire_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    node = Node(
        id='node-rb',
        name='n3',
        url='http://agent',
        token='tok',  # noqa: S106
    )
    peer = Peer(
        node=node,
        user=user,
        status='pending_delete',
        psk_key='p',
    )
    db.add_all([node, user, peer])
    await db.commit()
    user_id = user.id
    peer_id = peer.id
    db.expire_all()

    reloaded_user = await _load_user_with_peers(db, user_id)
    await apply_local_lifecycle_state(db, reloaded_user, local_total_bytes=0)
    await db.commit()
    db.expire_all()

    reloaded_peer = await db.get(Peer, peer_id)
    assert reloaded_peer is not None
    assert reloaded_peer.status == 'pending_delete'


async def test_enforce_local_lifecycle_for_user_skips_remnawave_user(
    db: AsyncSession,
) -> None:
    user = _make_user(
        id='u-rw-protected',
        expire_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    db.add(user)
    await db.flush()
    db.add(
        RemnawaveUser(
            user_id=user.id,
            remnawave_uuid='uuid-rw',
            username='rw-user',
            status='ACTIVE',
        )
    )
    await db.commit()
    user_id = user.id
    db.expire_all()

    affected = await enforce_local_lifecycle_for_user(db, user_id)
    await db.commit()
    db.expire_all()

    reloaded = await db.get(User, user_id)
    assert reloaded is not None
    assert affected == set()
    assert reloaded.lifecycle_status == 'active'
    assert reloaded.is_blocked is False


async def test_enforce_local_lifecycle_for_user_returns_none_for_missing(
    db: AsyncSession,
) -> None:
    assert await enforce_local_lifecycle_for_user(db, 'missing') == set()


async def test_reset_local_traffic_usage_clears_rows_and_stamps_reset_at(
    db: AsyncSession,
) -> None:
    user = _make_user(id='u-reset', traffic_reset_at=None)
    db.add(user)
    await db.flush()
    today = now().date()
    yesterday = today - timedelta(days=1)
    db.add_all(
        [
            LocalAmneziawgUserLifetimeTraffic(
                user_id=user.id,
                rx_bytes=100,
                tx_bytes=200,
                total_bytes=300,
                updated_at=now(),
            ),
            LocalAmneziawgUserNodeLifetimeTraffic(
                user_id=user.id,
                node_id='n1',
                rx_bytes=100,
                tx_bytes=200,
                total_bytes=300,
                updated_at=now(),
            ),
            LocalAmneziawgUserDailyTraffic(
                user_id=user.id,
                day=today,
                rx_bytes=10,
                tx_bytes=20,
                total_bytes=30,
                updated_at=now(),
            ),
            LocalAmneziawgUserNodeDailyTraffic(
                user_id=user.id,
                node_id='n1',
                day=today,
                rx_bytes=10,
                tx_bytes=20,
                total_bytes=30,
                updated_at=now(),
            ),
            LocalAmneziawgUserDailyTraffic(
                user_id=user.id,
                day=yesterday,
                rx_bytes=5,
                tx_bytes=5,
                total_bytes=10,
                updated_at=now(),
            ),
            LocalAmneziawgUserNodeDailyTraffic(
                user_id=user.id,
                node_id='n1',
                day=yesterday,
                rx_bytes=5,
                tx_bytes=5,
                total_bytes=10,
                updated_at=now(),
            ),
        ]
    )
    await db.commit()
    user_id = user.id
    db.expire_all()

    reloaded = await db.get(User, user_id)
    assert reloaded is not None
    await reset_local_traffic_usage(db, reloaded)
    await db.commit()
    db.expire_all()

    lifetime = await load_local_total_bytes(db, user_id)
    assert lifetime == 0

    daily_rows = (
        (
            await db.execute(
                select(LocalAmneziawgUserDailyTraffic).where(
                    LocalAmneziawgUserDailyTraffic.user_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    node_daily_rows = (
        (
            await db.execute(
                select(LocalAmneziawgUserNodeDailyTraffic).where(
                    LocalAmneziawgUserNodeDailyTraffic.user_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert {row.day for row in daily_rows} == {yesterday}
    assert {row.day for row in node_daily_rows} == {yesterday}

    refreshed = await db.get(User, user_id)
    assert refreshed is not None
    assert refreshed.traffic_reset_at is not None
    expected = (now() - timedelta(minutes=1)).replace(tzinfo=None)
    assert refreshed.traffic_reset_at >= expected


# ── Admin API tests ────────────────────────────────────────────────────────────


async def _create_local_user(client: AsyncClient, headers: dict[str, str]) -> dict:
    resp = await client.post('/api/users', json={'name': 'lifecycle-user'}, headers=headers)
    assert resp.status_code in (HTTPStatus.OK, HTTPStatus.CREATED), resp.text
    return resp.json()


async def test_list_users_includes_lifecycle_brief_for_local_user(
    client: AsyncClient, auth_headers
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)

    resp = await client.get('/api/users', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    found = next(u for u in resp.json() if u['id'] == body['id'])
    assert found['lifecycle'] == {
        'source': 'local',
        'status': 'active',
        'expire_at': None,
        'traffic_limit_bytes': 0,
        'traffic_reset_policy': 'manual',
        'traffic_reset_at': None,
        'blocked_reason': None,
    }
    assert found['public_token']
    assert found['traffic_reset_policy'] == 'manual'


async def test_update_local_lifecycle_extends_expiry(client: AsyncClient, auth_headers) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    future = (now() + timedelta(days=30)).isoformat()

    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={'expire_at': future, 'traffic_limit_bytes': 0, 'traffic_reset_policy': 'manual'},
        headers=headers,
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    data = resp.json()
    assert data['expire_at'].startswith(future[:19])
    assert data['lifecycle_status'] == 'active'


async def test_update_local_lifecycle_set_limit_blocks_user_and_marks_peers(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    db.add(
        Node(
            id='node-lc-limit',
            name='node-lc-limit',
            url='http://agent',
            token='tok',  # noqa: S106
        )
    )
    await db.commit()

    body = await _create_local_user(client, headers)
    user_id = body['id']

    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=10,
            tx_bytes=20,
            total_bytes=30,
            updated_at=now(),
        )
    )
    await db.commit()

    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={
            'expire_at': None,
            'traffic_limit_bytes': 10,
            'traffic_reset_policy': 'manual',
        },
        headers=headers,
    )

    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['lifecycle_status'] == 'limited'
    assert data['is_blocked'] is True

    db.expire_all()
    peer_statuses = (
        (await db.execute(select(Peer.status).where(Peer.user_id == user_id))).scalars().all()
    )
    assert peer_statuses
    assert all(status == 'pending_delete' for status in peer_statuses)


async def test_update_local_lifecycle_clear_limit_restores_active(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']

    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=100,
            tx_bytes=200,
            total_bytes=300,
            updated_at=now(),
        )
    )
    await db.commit()

    # First set a tight limit, then clear it.
    await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={
            'expire_at': None,
            'traffic_limit_bytes': 100,
            'traffic_reset_policy': 'manual',
        },
        headers=headers,
    )
    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={'expire_at': None, 'traffic_limit_bytes': 0, 'traffic_reset_policy': 'manual'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['lifecycle_status'] == 'active'
    assert data['is_blocked'] is False


async def test_update_local_lifecycle_rejects_remnawave_user(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    db.add(
        RemnawaveUser(
            user_id=user_id,
            remnawave_uuid='uuid-rw-lc',
            username='rw-lc',
            status='ACTIVE',
        )
    )
    await db.commit()

    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={'expire_at': None, 'traffic_limit_bytes': 1, 'traffic_reset_policy': 'manual'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.CONFLICT
    assert 'Remnawave-managed' in resp.json()['detail']


async def test_update_local_lifecycle_rejects_unknown_policy() -> None:
    from app.models import LocalUserLifecycleUpdate

    with pytest.raises(ValueError):
        LocalUserLifecycleUpdate.model_validate(
            {
                'expire_at': None,
                'traffic_limit_bytes': 0,
                'traffic_reset_policy': 'every_minute',
            }
        )


async def test_update_local_lifecycle_requires_auth(client: AsyncClient) -> None:
    resp = await client.put(
        '/api/users/missing/lifecycle',
        json={'expire_at': None, 'traffic_limit_bytes': 0, 'traffic_reset_policy': 'manual'},
    )
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_unblock_returns_409_when_lifecycle_blocks_user(
    client: AsyncClient, auth_headers
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']

    past = (now() - timedelta(days=1)).isoformat()
    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={'expire_at': past, 'traffic_limit_bytes': 0, 'traffic_reset_policy': 'manual'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['lifecycle_status'] == 'expired'

    resp = await client.put(f'/api/users/{user_id}/unblock', headers=headers)
    assert resp.status_code == HTTPStatus.CONFLICT
    assert 'lifecycle' in resp.json()['detail'].lower()


async def test_reset_local_traffic_clears_usage_and_unblocks_limited_user(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=100,
            tx_bytes=200,
            total_bytes=300,
            updated_at=now(),
        )
    )
    await db.commit()

    await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={
            'expire_at': None,
            'traffic_limit_bytes': 100,
            'traffic_reset_policy': 'manual',
        },
        headers=headers,
    )

    resp = await client.post(f'/api/users/{user_id}/lifecycle/reset-traffic', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['lifecycle_status'] == 'active'
    assert data['is_blocked'] is False
    assert data['traffic_reset_at'] is not None

    lifetime = await load_local_total_bytes(db, user_id)
    assert lifetime == 0


async def test_reset_local_traffic_blocked_when_policy_no_reset(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=100,
            tx_bytes=200,
            total_bytes=300,
            updated_at=now(),
        )
    )
    await db.commit()

    await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={
            'expire_at': None,
            'traffic_limit_bytes': 100,
            'traffic_reset_policy': 'no_reset',
        },
        headers=headers,
    )

    resp = await client.post(f'/api/users/{user_id}/lifecycle/reset-traffic', headers=headers)
    assert resp.status_code == HTTPStatus.CONFLICT
    assert 'reset is disabled' in resp.json()['detail'].lower()

    # Usage is still there.
    assert await load_local_total_bytes(db, user_id) == 300


async def test_reset_local_traffic_rejects_remnawave_user(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    db.add(
        RemnawaveUser(
            user_id=user_id,
            remnawave_uuid='uuid-rw-rt',
            username='rw-rt',
            status='ACTIVE',
        )
    )
    await db.commit()

    resp = await client.post(f'/api/users/{user_id}/lifecycle/reset-traffic', headers=headers)
    assert resp.status_code == HTTPStatus.CONFLICT


async def test_regenerate_public_link_rotates_token_and_returns_url(
    client: AsyncClient, auth_headers
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    original_token = body['public_token']
    assert original_token

    resp = await client.post(f'/api/users/{user_id}/public-link/regenerate', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['public_token']
    assert data['public_token'] != original_token
    assert secrets.token_urlsafe(24)  # sanity check: format is url-safe
    # Length sanity: token_urlsafe(24) yields ~32 chars.
    assert len(data['public_token']) >= 24
    assert data['public_url'] == f'/u/{data["public_token"]}'

    # Listing users should reflect the rotated token.
    listing = await client.get('/api/users', headers=headers)
    refreshed = next(u for u in listing.json() if u['id'] == user_id)
    assert refreshed['public_token'] == data['public_token']


async def test_regenerate_public_link_rejects_remnawave_user(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    db.add(
        RemnawaveUser(
            user_id=user_id,
            remnawave_uuid='uuid-rw-rot',
            username='rw-rot',
            status='ACTIVE',
        )
    )
    await db.commit()

    resp = await client.post(f'/api/users/{user_id}/public-link/regenerate', headers=headers)
    assert resp.status_code == HTTPStatus.CONFLICT


# ── Public user page ───────────────────────────────────────────────────────────


async def test_pub_user_info_accepts_public_token(client: AsyncClient, auth_headers) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    token = body['public_token']

    resp = await client.get(f'/pub/u/{token}/info')
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['user_name'] == 'lifecycle-user'
    assert data['status'] == {'code': 'active', 'reason': None}
    assert data['subscription'] == {
        'managed': False,
        'expire_at': None,
        'last_synced_at': None,
    }


async def test_pub_user_info_local_user_with_expiry_reports_it(
    client: AsyncClient, auth_headers
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    future = (now() + timedelta(days=10)).isoformat()
    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={'expire_at': future, 'traffic_limit_bytes': 0, 'traffic_reset_policy': 'manual'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    token = resp.json()['public_token']

    info = await client.get(f'/pub/u/{token}/info')
    assert info.status_code == HTTPStatus.OK
    payload = info.json()
    assert payload['blocked'] is False
    assert payload['status'] == {'code': 'active', 'reason': None}
    assert payload['subscription']['expire_at'].startswith(future[:19])


async def test_pub_user_info_local_user_expired_reports_blocked_status(
    client: AsyncClient, auth_headers
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    past = (now() - timedelta(days=1)).isoformat()
    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={'expire_at': past, 'traffic_limit_bytes': 0, 'traffic_reset_policy': 'manual'},
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    token = resp.json()['public_token']

    info = await client.get(f'/pub/u/{token}/info')
    assert info.status_code == HTTPStatus.OK
    payload = info.json()
    assert payload['blocked'] is True
    assert payload['status'] == {'code': 'expired', 'reason': 'expired'}
    assert payload['nodes'] == []


async def test_pub_user_info_local_user_limited_reports_limit_and_limited_status(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    db.add(
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user_id,
            rx_bytes=10,
            tx_bytes=20,
            total_bytes=30,
            updated_at=now(),
        )
    )
    await db.commit()

    resp = await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={
            'expire_at': None,
            'traffic_limit_bytes': 10,
            'traffic_reset_policy': 'manual',
        },
        headers=headers,
    )
    assert resp.status_code == HTTPStatus.OK
    token = resp.json()['public_token']

    info = await client.get(f'/pub/u/{token}/info')
    assert info.status_code == HTTPStatus.OK
    payload = info.json()
    assert payload['blocked'] is True
    assert payload['status'] == {'code': 'limited', 'reason': 'limited'}
    assert payload['traffic']['limit_bytes'] == 10
    assert payload['traffic']['used_bytes'] == 30


async def test_pub_user_info_404_for_unknown_token(client: AsyncClient) -> None:
    resp = await client.get('/pub/u/no-such-token/info')
    assert resp.status_code == HTTPStatus.NOT_FOUND


async def test_pub_user_daily_traffic_respects_traffic_reset_at(
    client: AsyncClient, auth_headers, db
) -> None:
    headers = auth_headers
    body = await _create_local_user(client, headers)
    user_id = body['id']
    today = now().date()
    old_day = today - timedelta(days=10)
    new_day = today - timedelta(days=1)

    db.add_all(
        [
            LocalAmneziawgUserDailyTraffic(
                user_id=user_id,
                day=old_day,
                rx_bytes=1,
                tx_bytes=1,
                total_bytes=2,
                updated_at=now(),
            ),
            LocalAmneziawgUserDailyTraffic(
                user_id=user_id,
                day=new_day,
                rx_bytes=5,
                tx_bytes=5,
                total_bytes=10,
                updated_at=now(),
            ),
        ]
    )
    await db.commit()

    before = await client.get(f'/api/users/{user_id}/local-traffic/daily?days=30', headers=headers)
    assert before.status_code == HTTPStatus.OK
    before_days = {row['day'] for row in before.json()}
    assert old_day.isoformat() in before_days
    assert new_day.isoformat() in before_days

    await client.put(
        f'/api/users/{user_id}/lifecycle',
        json={
            'expire_at': None,
            'traffic_limit_bytes': 10_000_000,
            'traffic_reset_policy': 'manual',
        },
        headers=headers,
    )
    reset = await client.post(f'/api/users/{user_id}/lifecycle/reset-traffic', headers=headers)
    assert reset.status_code == HTTPStatus.OK
    assert reset.json()['traffic_reset_at'] is not None

    resp = await client.get(f'/api/users/{user_id}/local-traffic/daily?days=30', headers=headers)
    assert resp.status_code == HTTPStatus.OK
    after_days = {row['day'] for row in resp.json()}
    assert old_day.isoformat() not in after_days
    assert new_day.isoformat() not in after_days


# ── Worker-side enforcement ────────────────────────────────────────────────────


async def _post_sync_result(
    client: AsyncClient, headers: dict[str, str], node_id: str, peers: list[dict]
):
    return await client.post(
        f'/internal/worker/nodes/{node_id}/sync-result',
        json={
            'interface': {
                'listen_port': 51820,
                'private_key': 'node-private-key',
                'public_key': 'node-public-key',
            },
            'peers': peers,
        },
        headers=headers,
    )


@pytest.mark.usefixtures('mock_sync_node_enqueue')
async def test_node_sync_result_enforces_local_limit_and_enqueues_sync(
    client: AsyncClient, db, worker_headers
) -> None:
    node = Node(
        id='node-sync-lc',
        name='node-sync-lc',
        url='http://agent',
        token='tok',  # noqa: S106
    )
    user = _make_user(
        id='u-sync-limited',
        traffic_limit_bytes=1_000,
        public_key='pk-sync-limited',
    )
    peer = Peer(
        node_id=node.id,
        user_id=user.id,
        status='pending',
        psk_key='psk',
    )
    db.add_all([node, user, peer])
    await db.flush()
    peer.raw_rx = 100
    peer.raw_tx = 100
    await db.commit()
    user_id = user.id
    peer_id = peer.id

    with patch(
        'app.routers.internal_worker.enqueue_remnawave_disable_user',
        new=AsyncMock(),
    ) as enqueue_disable:
        resp = await _post_sync_result(
            client,
            worker_headers,
            node.id,
            [
                {
                    'public_key': 'pk-sync-limited',
                    'status': 'active',
                    'rx_bytes': 700,
                    'tx_bytes': 700,
                }
            ],
        )

    assert resp.status_code == HTTPStatus.OK
    enqueue_disable.assert_not_called()

    db.expire_all()
    reloaded = await db.get(User, user_id)
    assert reloaded is not None
    reloaded_peer = await db.get(Peer, peer_id)
    assert reloaded_peer is not None
    assert reloaded.lifecycle_status == 'limited'
    assert reloaded.is_blocked is True
    assert reloaded_peer.status == 'pending_delete'


@pytest.mark.usefixtures('mock_sync_node_enqueue')
async def test_node_sync_result_does_not_enforce_lifecycle_for_remnawave_user(
    client: AsyncClient, db, worker_headers
) -> None:
    node = Node(
        id='node-sync-rw',
        name='node-sync-rw',
        url='http://agent',
        token='tok',  # noqa: S106
    )
    user = _make_user(
        id='u-sync-rw',
        traffic_limit_bytes=1_000,
        public_key='pk-sync-rw',
    )
    peer = Peer(
        node_id=node.id,
        user_id=user.id,
        status='pending',
        psk_key='psk',
    )
    db.add_all([node, user, peer])
    await db.flush()
    db.add(
        RemnawaveUser(
            user_id=user.id,
            remnawave_uuid='uuid-sync-rw',
            username='rw-sync',
            status='ACTIVE',
        )
    )
    await db.flush()
    peer.raw_rx = 100
    peer.raw_tx = 100
    await db.commit()
    user_id = user.id
    peer_id = peer.id

    with patch(
        'app.routers.internal_worker.enqueue_remnawave_disable_user',
        new=AsyncMock(),
    ) as enqueue_disable:
        resp = await _post_sync_result(
            client,
            worker_headers,
            node.id,
            [
                {
                    'public_key': 'pk-sync-rw',
                    'status': 'active',
                    'rx_bytes': 600,
                    'tx_bytes': 500,
                }
            ],
        )

    assert resp.status_code == HTTPStatus.OK
    enqueue_disable.assert_not_called()

    db.expire_all()
    reloaded = await db.get(User, user_id)
    assert reloaded is not None
    reloaded_peer = await db.get(Peer, peer_id)
    assert reloaded_peer is not None
    assert reloaded.lifecycle_status == 'active'
    assert reloaded.is_blocked is False
    assert reloaded_peer.status == 'active'
