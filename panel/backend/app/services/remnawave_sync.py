from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import LocalAmneziawgUserLifetimeTraffic, Peer, RemnawaveUser, User
from app.schemas.worker import RemnawaveUserIn
from app.services.operations import enqueue_operation, new_operation


def now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def remnawave_blocked(data: RemnawaveUser | RemnawaveUserIn) -> bool:
    if data.status in {'DISABLED', 'LIMITED', 'EXPIRED'}:
        return True
    expire_at = aware(data.expire_at)
    return expire_at is not None and expire_at <= now()


def remnawave_combined_limited(row: RemnawaveUser, local_total_bytes: int) -> bool:
    return (
        row.traffic_limit_bytes > 0
        and row.traffic_used_bytes + local_total_bytes >= row.traffic_limit_bytes
    )


async def enqueue_sync_nodes(db: AsyncSession, node_ids: set[str]) -> None:
    from app.routers import internal_worker

    for node_id in sorted(node_ids):
        await enqueue_operation(
            db,
            new_operation('sync_node', 'node', node_id),
            internal_worker.enqueue_sync_node,
            node_id,
        )


async def enqueue_remnawave_disable_users(db: AsyncSession, user_uuids: set[str]) -> None:
    from app.routers import internal_worker

    for user_uuid in sorted(user_uuids):
        await enqueue_operation(
            db,
            new_operation('remnawave_disable_user', 'remnawave_user', user_uuid),
            internal_worker.enqueue_remnawave_disable_user,
            user_uuid,
        )


def apply_remnawave_profile(row: RemnawaveUser, data: RemnawaveUserIn) -> None:
    row.remnawave_id = data.id
    row.short_uuid = data.short_uuid
    row.username = data.username
    row.status = data.status
    row.expire_at = data.expire_at
    row.email = data.email
    row.tag = data.tag
    row.telegram_id = data.telegram_id
    row.description = data.description
    row.traffic_limit_bytes = data.traffic_limit_bytes
    row.traffic_limit_strategy = data.traffic_limit_strategy
    row.traffic_used_bytes = data.traffic_used_bytes
    row.lifetime_used_traffic_bytes = data.lifetime_used_traffic_bytes
    row.last_traffic_reset_at = data.last_traffic_reset_at
    row.online_at = data.online_at
    row.first_connected_at = data.first_connected_at
    row.last_connected_node_uuid = data.last_connected_node_uuid
    row.hwid_device_limit = data.hwid_device_limit
    row.external_squad_uuid = data.external_squad_uuid
    row.active_internal_squads_json = data.active_internal_squads_json
    row.subscription_url_encrypted = data.subscription_url
    row.last_synced_at = now()
    row.sync_status = 'synced'
    row.sync_reason = None
    row.sync_error = None
    row.delete_requested_at = None


def apply_remnawave_lifecycle(row: RemnawaveUser, data: RemnawaveUserIn) -> set[str]:
    affected_node_ids: set[str] = set()
    should_block = remnawave_blocked(data)
    if row.user.is_blocked == should_block:
        return affected_node_ids

    row.user.is_blocked = should_block
    for peer in row.user.peers:
        if should_block:
            if peer.status != 'pending_delete':
                peer.status = 'pending_delete'
                affected_node_ids.add(peer.node_id)
        elif peer.status in {'pending_delete', 'deleted'}:
            peer.status = 'pending'
            affected_node_ids.add(peer.node_id)
    return affected_node_ids


async def enforce_remnawave_combined_limit(
    db: AsyncSession, row: RemnawaveUser
) -> tuple[set[str], set[str]]:
    local_total = await db.scalar(
        select(LocalAmneziawgUserLifetimeTraffic.total_bytes).where(
            LocalAmneziawgUserLifetimeTraffic.user_id == row.user_id
        )
    )
    if not remnawave_combined_limited(row, local_total or 0):
        return set(), set()

    remote_disable_uuids = set()
    if row.status != 'DISABLED':
        remote_disable_uuids.add(row.remnawave_uuid)
    row.user.is_blocked = True
    peers = (await db.execute(select(Peer).where(Peer.user_id == row.user_id))).scalars().all()
    affected_node_ids: set[str] = set()
    for peer in peers:
        if peer.status != 'pending_delete':
            peer.status = 'pending_delete'
            affected_node_ids.add(peer.node_id)
    return affected_node_ids, remote_disable_uuids


async def enforce_remnawave_combined_limit_for_user(
    db: AsyncSession, user_id: str
) -> tuple[set[str], set[str]]:
    row = (
        await db.execute(
            select(RemnawaveUser)
            .where(RemnawaveUser.user_id == user_id)
            .options(selectinload(RemnawaveUser.user))
        )
    ).scalar_one_or_none()
    if row is None:
        return set(), set()
    return await enforce_remnawave_combined_limit(db, row)


def mark_remnawave_user_stale(
    row: RemnawaveUser, *, reason: str = 'remote user missing'
) -> set[str]:
    affected_node_ids: set[str] = set()
    already_stale = (
        row.sync_status == 'stale'
        and row.sync_reason == reason
        and row.sync_error is None
        and row.user.is_blocked
        and all(peer.status == 'pending_delete' for peer in row.user.peers)
    )
    row.sync_status = 'stale'
    row.sync_reason = reason
    row.sync_error = None
    row.user.is_blocked = True
    for peer in row.user.peers:
        if peer.status != 'pending_delete':
            peer.status = 'pending_delete'
            affected_node_ids.add(peer.node_id)
    if already_stale and not affected_node_ids:
        return set()
    return affected_node_ids


async def reconcile_missing_remnawave_users(
    db: AsyncSession,
    seen_uuids: set[str],
    *,
    reason: str = 'remote user missing',
) -> set[str]:
    query = select(RemnawaveUser).options(selectinload(RemnawaveUser.user).selectinload(User.peers))
    if seen_uuids:
        query = query.where(~RemnawaveUser.remnawave_uuid.in_(seen_uuids))
    rows = (await db.execute(query)).scalars().all()
    affected_node_ids: set[str] = set()
    for row in rows:
        affected_node_ids.update(mark_remnawave_user_stale(row, reason=reason))
    return affected_node_ids


async def purge_confirmed_remnawave_deletes(db: AsyncSession) -> int:
    rows = (
        (
            await db.execute(
                select(RemnawaveUser)
                .where(RemnawaveUser.delete_requested_at.isnot(None))
                .options(selectinload(RemnawaveUser.user).selectinload(User.peers))
            )
        )
        .scalars()
        .all()
    )
    purged = 0
    for row in rows:
        if row.user.peers and all(peer.status == 'deleted' for peer in row.user.peers):
            await db.delete(row.user)
            purged += 1
    return purged
