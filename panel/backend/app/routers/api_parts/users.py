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
    Node,
    Peer,
    PeerBrief,
    PeerTrafficSample,
    RemnawaveUserBrief,
    User,
    UserIn,
    UserSchema,
    UserWithPeers,
)
from app.routers.api_parts.common import DB, guard_not_remnawave_managed
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


@router.get('/users', response_model=list[UserWithPeers])
async def api_list_users(db: DB):
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
                peers=[
                    PeerBrief(
                        node_id=p.node_id,
                        node_name=p.node.name,
                        status=p.status,
                        last_handshake=p.last_handshake,
                    )
                    for p in u.peers
                ],
                remnawave=rw_brief,
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

    user.is_blocked = True
    node_ids = [peer.node_id for peer in user.peers]
    for peer in user.peers:
        peer.status = 'pending_delete'
    await db.commit()
    for node_id in node_ids:
        operation = new_operation('sync_node', 'node', node_id)
        from app.routers import api as api_router

        await enqueue_operation(db, operation, api_router.enqueue_sync_node, node_id)
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

    user.is_blocked = False
    node_ids = [peer.node_id for peer in user.peers]
    for peer in user.peers:
        if peer.status == 'pending_delete':
            peer.status = 'pending'
    await db.commit()
    for node_id in node_ids:
        operation = new_operation('sync_node', 'node', node_id)
        from app.routers import api as api_router

        await enqueue_operation(db, operation, api_router.enqueue_sync_node, node_id)
    return user


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
    await get_user_or_404(user_id, db)
    since = (datetime.now(UTC) - timedelta(days=days)).date()
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
    await get_user_or_404(user_id, db)
    since = (datetime.now(UTC) - timedelta(days=days)).date()
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
