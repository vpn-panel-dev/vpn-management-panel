from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import selectinload

from app.models import (
    LocalAmneziawgUsageDailyTotals,
    LocalAmneziawgUsageNodeDailyTotals,
    LocalAmneziawgUsageNodeTotals,
    LocalAmneziawgUsageTotals,
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    LocalUserLifecycle,
    LocalUserLifecycleUpdate,
    Node,
    Peer,
    PeerBrief,
    PeerTrafficSample,
    RegeneratedPublicLink,
    RemnawaveUserBrief,
    User,
    UserIn,
    UserSchema,
    UserWithPeers,
)
from app.routers.api_parts.common import DB, guard_not_remnawave_managed
from app.services.local_lifecycle import (
    apply_local_lifecycle_state,
    load_local_total_bytes,
    local_user_blocked_reason,
    now,
    reset_local_traffic_usage,
)
from app.services.online import is_peer_online, online_threshold_seconds
from app.services.operations import enqueue_operation, new_operation
from app.services.users import create_local_user

router = APIRouter()


def _remnawave_blocked_reason(rw, local_total: int) -> str | None:
    if rw.delete_requested_at is not None:
        return 'deleted'
    if rw.sync_status in {'missing', 'stale'}:
        return 'deleted'
    status_reasons = {
        'DISABLED': 'disabled',
        'LIMITED': 'limited',
        'EXPIRED': 'expired',
    }
    if reason := status_reasons.get(rw.status):
        return reason
    if rw.traffic_limit_bytes > 0 and rw.traffic_used_bytes + local_total >= rw.traffic_limit_bytes:
        return 'limited'
    expire_at = rw.expire_at
    if expire_at is not None:
        if expire_at.tzinfo is None:
            expire_at = expire_at.replace(tzinfo=UTC)
        if expire_at <= datetime.now(UTC):
            return 'expired'
    return None


async def get_user_or_404(user_id: str, db: DB) -> User:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user


def _local_lifecycle_brief(user: User, local_total: int) -> LocalUserLifecycle:
    return LocalUserLifecycle(
        status=user.lifecycle_status,
        expire_at=user.expire_at,
        traffic_limit_bytes=user.traffic_limit_bytes,
        traffic_reset_policy=user.traffic_reset_policy,
        traffic_reset_at=user.traffic_reset_at,
        blocked_reason=local_user_blocked_reason(user, local_total),
    )


async def _enqueue_sync_nodes_for_user(db: DB, user: User) -> None:
    node_ids = sorted({peer.node_id for peer in user.peers})
    for node_id in node_ids:
        operation = new_operation('sync_node', 'node', node_id)
        from app.routers import api as api_router

        await enqueue_operation(db, operation, api_router.enqueue_sync_node, node_id)


@router.get('/users', response_model=list[UserWithPeers])
async def api_list_users(db: DB):
    threshold_seconds = await online_threshold_seconds(db)
    rows = (
        (
            await db.execute(
                select(User).options(
                    selectinload(User.peers).selectinload(Peer.node),
                    selectinload(User.remnawave_user),
                )
            )
        )
        .scalars()
        .all()
    )
    local_traffic_rows = (
        (await db.execute(select(LocalAmneziawgUserLifetimeTraffic))).scalars().all()
    )
    local_traffic_by_user_id = {
        row.user_id: LocalAmneziawgUsageTotals(
            user_id=row.user_id,
            rx_bytes=row.rx_bytes,
            tx_bytes=row.tx_bytes,
            total_bytes=row.total_bytes,
            updated_at=row.updated_at,
        )
        for row in local_traffic_rows
    }
    result = []
    for u in rows:
        rw_brief = None
        local_traffic = local_traffic_by_user_id.get(u.id)
        peer_briefs = [
            PeerBrief(
                node_id=p.node_id,
                node_name=p.node.name,
                status=p.status,
                last_handshake=p.last_handshake,
                endpoint=p.endpoint,
                online=is_peer_online(p, threshold_seconds),
            )
            for p in u.peers
        ]
        if u.remnawave_user is not None:
            rw = u.remnawave_user
            local_total = local_traffic.total_bytes if local_traffic else 0
            rw_brief = RemnawaveUserBrief(
                uuid=rw.remnawave_uuid,
                username=rw.username,
                status=rw.status,
                expire_at=rw.expire_at,
                email=rw.email,
                tag=rw.tag,
                traffic_used_bytes=rw.traffic_used_bytes,
                traffic_limit_bytes=rw.traffic_limit_bytes,
                local_amneziawg_traffic_used_bytes=local_total,
                combined_traffic_used_bytes=rw.traffic_used_bytes + local_total,
                blocked_reason=_remnawave_blocked_reason(rw, local_total),
                delete_requested_at=rw.delete_requested_at,
                last_synced_at=rw.last_synced_at,
                sync_status=rw.sync_status,
                sync_reason=rw.sync_reason,
                sync_error=rw.sync_error,
            )
        result.append(
            UserWithPeers(
                **UserSchema.model_validate(u).model_dump(),
                peers=peer_briefs,
                online=any(peer.online for peer in peer_briefs),
                remnawave=rw_brief,
                lifecycle=_local_lifecycle_brief(
                    u, local_traffic.total_bytes if local_traffic else 0
                ),
                local_traffic=local_traffic,
            )
        )
    return result


@router.post('/users', response_model=UserSchema, status_code=201)
async def api_add_user(data: UserIn, db: DB):
    user = await create_local_user(db, data.name)
    await db.commit()
    await db.refresh(user)
    return user


@router.put('/users/{user_id}/block', response_model=UserSchema)
async def api_block_user(user_id: str, db: DB):
    user = await db.get(
        User,
        user_id,
        options=[selectinload(User.peers), selectinload(User.remnawave_user)],
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await guard_not_remnawave_managed(user)

    user.lifecycle_status = 'blocked'
    await apply_local_lifecycle_state(db, user)
    await db.commit()
    await _enqueue_sync_nodes_for_user(db, user)
    return user


@router.put('/users/{user_id}/unblock', response_model=UserSchema)
async def api_unblock_user(user_id: str, db: DB):
    user = await db.get(
        User,
        user_id,
        options=[selectinload(User.peers), selectinload(User.remnawave_user)],
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await guard_not_remnawave_managed(user)

    local_total = await load_local_total_bytes(db, user.id)
    if local_user_blocked_reason(user, local_total) in {'expired', 'limited'}:
        raise HTTPException(status_code=409, detail='User is blocked by lifecycle constraints')

    user.lifecycle_status = 'active'
    await apply_local_lifecycle_state(db, user, local_total_bytes=local_total)
    await db.commit()
    await _enqueue_sync_nodes_for_user(db, user)
    return user


@router.put('/users/{user_id}/lifecycle', response_model=UserSchema)
async def api_update_local_lifecycle(user_id: str, data: LocalUserLifecycleUpdate, db: DB):
    user = await db.get(
        User,
        user_id,
        options=[selectinload(User.peers), selectinload(User.remnawave_user)],
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await guard_not_remnawave_managed(user)

    user.expire_at = data.expire_at
    user.traffic_limit_bytes = data.traffic_limit_bytes
    user.traffic_reset_policy = data.traffic_reset_policy
    await apply_local_lifecycle_state(db, user)
    await db.commit()
    await _enqueue_sync_nodes_for_user(db, user)
    return user


@router.post('/users/{user_id}/lifecycle/reset-traffic', response_model=UserSchema)
async def api_reset_local_traffic(user_id: str, db: DB):
    user = await db.get(
        User,
        user_id,
        options=[selectinload(User.peers), selectinload(User.remnawave_user)],
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await guard_not_remnawave_managed(user)
    if user.traffic_reset_policy != 'manual':
        raise HTTPException(status_code=409, detail='Traffic reset is disabled for this user')

    await reset_local_traffic_usage(db, user, now())
    await apply_local_lifecycle_state(db, user, local_total_bytes=0)
    await db.commit()
    await _enqueue_sync_nodes_for_user(db, user)
    return user


@router.post('/users/{user_id}/public-link/regenerate', response_model=RegeneratedPublicLink)
async def api_regenerate_public_link(user_id: str, db: DB):
    user = await db.get(User, user_id, options=[selectinload(User.remnawave_user)])
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await guard_not_remnawave_managed(user)

    from app.models import _public_token

    user.public_token = _public_token()
    await db.commit()
    return RegeneratedPublicLink(
        public_token=user.public_token, public_url=f'/u/{user.public_token}'
    )


@router.delete('/users/{user_id}', status_code=204)
async def api_delete_user(user_id: str, db: DB):
    user = await db.get(
        User,
        user_id,
        options=[selectinload(User.peers), selectinload(User.remnawave_user)],
    )
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await guard_not_remnawave_managed(user)

    if not user.public_key:
        raise HTTPException(status_code=400, detail='User has no public key')
    node_ids = [peer.node_id for peer in user.peers]
    await db.delete(user)
    await db.commit()
    for node_id in node_ids:
        operation = new_operation('sync_node', 'node', node_id)
        from app.routers import api as api_router

        await enqueue_operation(db, operation, api_router.enqueue_sync_node, node_id)


@router.get('/users/{user_id}/traffic')
async def api_user_traffic(user_id: str, db: DB, days: int = 30):
    await get_user_or_404(user_id, db)

    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await db.execute(
            select(
                func.date(PeerTrafficSample.sampled_at).label('day'),
                func.sum(PeerTrafficSample.rx_bytes).label('rx'),
                func.sum(PeerTrafficSample.tx_bytes).label('tx'),
            )
            .join(Peer, PeerTrafficSample.peer_id == Peer.id)
            .where(Peer.user_id == user_id, PeerTrafficSample.sampled_at >= since)
            .group_by(text('1'))
            .order_by(text('1'))
        )
    ).all()

    return [
        {
            'day': r.day.isoformat() if hasattr(r.day, 'isoformat') else str(r.day),
            'rx_bytes': int(r.rx),
            'tx_bytes': int(r.tx),
        }
        for r in rows
    ]


@router.get('/users/{user_id}/local-traffic', response_model=LocalAmneziawgUsageTotals)
async def api_user_local_traffic_lifetime(user_id: str, db: DB):
    await get_user_or_404(user_id, db)
    row = await db.scalar(
        select(LocalAmneziawgUserLifetimeTraffic).where(
            LocalAmneziawgUserLifetimeTraffic.user_id == user_id
        )
    )
    if row is None:
        return LocalAmneziawgUsageTotals(user_id=user_id)
    return LocalAmneziawgUsageTotals(
        user_id=user_id,
        rx_bytes=row.rx_bytes,
        tx_bytes=row.tx_bytes,
        total_bytes=row.total_bytes,
        updated_at=row.updated_at,
    )


@router.get(
    '/users/{user_id}/local-traffic/daily',
    response_model=list[LocalAmneziawgUsageDailyTotals],
)
async def api_user_local_traffic_daily(user_id: str, db: DB, days: int = 30):
    user = await get_user_or_404(user_id, db)
    since = (datetime.now(UTC) - timedelta(days=days)).date()
    if user.traffic_reset_at is not None:
        since = max(since, user.traffic_reset_at.date())
    rows = (
        (
            await db.execute(
                select(LocalAmneziawgUserDailyTraffic)
                .where(
                    LocalAmneziawgUserDailyTraffic.user_id == user_id,
                    LocalAmneziawgUserDailyTraffic.day >= since,
                )
                .order_by(LocalAmneziawgUserDailyTraffic.day)
            )
        )
        .scalars()
        .all()
    )
    return [
        LocalAmneziawgUsageDailyTotals(
            user_id=user_id,
            day=row.day,
            rx_bytes=row.rx_bytes,
            tx_bytes=row.tx_bytes,
            total_bytes=row.total_bytes,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get(
    '/users/{user_id}/local-traffic/nodes',
    response_model=list[LocalAmneziawgUsageNodeTotals],
)
async def api_user_local_traffic_nodes(user_id: str, db: DB):
    await get_user_or_404(user_id, db)
    rows = (
        await db.execute(
            select(LocalAmneziawgUserNodeLifetimeTraffic, Node)
            .join(Node, LocalAmneziawgUserNodeLifetimeTraffic.node_id == Node.id)
            .where(LocalAmneziawgUserNodeLifetimeTraffic.user_id == user_id)
            .order_by(Node.name, Node.id)
        )
    ).all()
    return [
        LocalAmneziawgUsageNodeTotals(
            user_id=user_id,
            node_id=node.id,
            node_name=node.name,
            rx_bytes=row.rx_bytes,
            tx_bytes=row.tx_bytes,
            total_bytes=row.total_bytes,
            updated_at=row.updated_at,
        )
        for row, node in rows
    ]


@router.get(
    '/users/{user_id}/local-traffic/nodes/daily',
    response_model=list[LocalAmneziawgUsageNodeDailyTotals],
)
async def api_user_local_traffic_nodes_daily(user_id: str, db: DB, days: int = 30):
    user = await get_user_or_404(user_id, db)
    since = (datetime.now(UTC) - timedelta(days=days)).date()
    if user.traffic_reset_at is not None:
        since = max(since, user.traffic_reset_at.date())
    rows = (
        await db.execute(
            select(LocalAmneziawgUserNodeDailyTraffic, Node)
            .join(Node, LocalAmneziawgUserNodeDailyTraffic.node_id == Node.id)
            .where(
                LocalAmneziawgUserNodeDailyTraffic.user_id == user_id,
                LocalAmneziawgUserNodeDailyTraffic.day >= since,
            )
            .order_by(LocalAmneziawgUserNodeDailyTraffic.day, Node.name, Node.id)
        )
    ).all()
    return [
        LocalAmneziawgUsageNodeDailyTotals(
            user_id=user_id,
            node_id=node.id,
            node_name=node.name,
            day=row.day,
            rx_bytes=row.rx_bytes,
            tx_bytes=row.tx_bytes,
            total_bytes=row.total_bytes,
            updated_at=row.updated_at,
        )
        for row, node in rows
    ]
