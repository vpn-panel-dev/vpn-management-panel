from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import RemnawaveUser, User
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


async def enqueue_sync_nodes(db: AsyncSession, node_ids: set[str]) -> None:
    from app.routers import internal_worker

    for node_id in sorted(node_ids):
        await enqueue_operation(
            db,
            new_operation('sync_node', 'node', node_id),
            internal_worker.enqueue_sync_node,
            node_id,
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
    row.sync_error = None
    row.delete_requested_at = None


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
