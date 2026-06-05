from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    User,
)


def aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def now() -> datetime:
    return datetime.now(UTC)


def local_user_expired(user: User, observed_at: datetime | None = None) -> bool:
    expire_at = aware(user.expire_at)
    if expire_at is None:
        return False
    return expire_at <= (observed_at or now())


def local_user_limited(user: User, local_total_bytes: int) -> bool:
    return user.traffic_limit_bytes > 0 and local_total_bytes >= user.traffic_limit_bytes


def local_user_blocked_reason(user: User, local_total_bytes: int) -> str | None:
    if local_user_expired(user):
        return 'expired'
    if local_user_limited(user, local_total_bytes):
        return 'limited'
    if user.lifecycle_status == 'blocked' or user.is_blocked:
        return 'blocked'
    return None


async def load_local_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.peers), selectinload(User.remnawave_user))
    )
    return result.scalar_one_or_none()


async def load_local_total_bytes(db: AsyncSession, user_id: str) -> int:
    total = await db.scalar(
        select(LocalAmneziawgUserLifetimeTraffic.total_bytes).where(
            LocalAmneziawgUserLifetimeTraffic.user_id == user_id
        )
    )
    return int(total or 0)


async def apply_local_lifecycle_state(
    db: AsyncSession, user: User, *, local_total_bytes: int | None = None
) -> set[str]:
    total = local_total_bytes
    if total is None:
        total = await load_local_total_bytes(db, user.id)

    if local_user_expired(user):
        desired_status = 'expired'
    elif local_user_limited(user, total):
        desired_status = 'limited'
    elif user.lifecycle_status == 'blocked':
        desired_status = 'blocked'
    else:
        desired_status = 'active'

    user.lifecycle_status = desired_status
    should_block = desired_status != 'active'
    user.is_blocked = should_block

    affected_node_ids: set[str] = set()
    for peer in user.peers:
        if should_block:
            if peer.status != 'pending_delete':
                peer.status = 'pending_delete'
                affected_node_ids.add(peer.node_id)
            continue
        if peer.status in {'pending_delete', 'deleted'}:
            peer.status = 'pending'
            affected_node_ids.add(peer.node_id)
    return affected_node_ids


async def enforce_local_lifecycle_for_user(db: AsyncSession, user_id: str) -> set[str]:
    user = await load_local_user(db, user_id)
    if user is None or user.remnawave_user is not None:
        return set()
    return await apply_local_lifecycle_state(db, user)


async def reset_local_traffic_usage(
    db: AsyncSession, user: User, observed_at: datetime | None = None
) -> None:
    reset_at = observed_at or now()
    await db.execute(
        delete(LocalAmneziawgUserLifetimeTraffic).where(
            LocalAmneziawgUserLifetimeTraffic.user_id == user.id
        )
    )
    await db.execute(
        delete(LocalAmneziawgUserNodeLifetimeTraffic).where(
            LocalAmneziawgUserNodeLifetimeTraffic.user_id == user.id
        )
    )
    await db.execute(
        delete(LocalAmneziawgUserDailyTraffic).where(
            LocalAmneziawgUserDailyTraffic.user_id == user.id,
            LocalAmneziawgUserDailyTraffic.day >= reset_at.date(),
        )
    )
    await db.execute(
        delete(LocalAmneziawgUserNodeDailyTraffic).where(
            LocalAmneziawgUserNodeDailyTraffic.user_id == user.id,
            LocalAmneziawgUserNodeDailyTraffic.day >= reset_at.date(),
        )
    )
    user.traffic_reset_at = reset_at
