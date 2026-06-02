from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LocalAmneziawgTrafficSettings, Peer


async def online_threshold_seconds(db: AsyncSession) -> int:
    threshold = await db.scalar(
        select(LocalAmneziawgTrafficSettings.peer_online_threshold_seconds).order_by(
            LocalAmneziawgTrafficSettings.created_at,
            LocalAmneziawgTrafficSettings.id,
        )
    )
    return threshold or 180


def is_peer_online(peer: Peer, threshold_seconds: int, now: datetime | None = None) -> bool:
    if peer.last_handshake is None:
        return False
    reference = now or datetime.now(UTC)
    last_handshake = peer.last_handshake
    if last_handshake.tzinfo is None:
        last_handshake = last_handshake.replace(tzinfo=UTC)
    return reference - last_handshake <= timedelta(seconds=threshold_seconds)
