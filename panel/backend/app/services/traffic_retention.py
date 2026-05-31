from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    LocalAmneziawgTrafficDelta,
    LocalAmneziawgTrafficSettings,
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Peer,
    PeerTrafficSample,
)


@dataclass(frozen=True)
class RawSampleRetentionResult:
    retention_days: int
    deleted: int
    disabled: bool
    cutoff: datetime | None = None


async def cleanup_raw_traffic_samples(
    db: AsyncSession, now: datetime | None = None
) -> RawSampleRetentionResult:
    settings = await LocalAmneziawgTrafficSettings.get_settings(db)
    retention_days = settings.raw_sample_retention_days
    if retention_days == 0:
        return RawSampleRetentionResult(retention_days=retention_days, deleted=0, disabled=True)

    cutoff = (now or datetime.now(UTC)) - timedelta(days=retention_days)
    sample_ids = await _deletable_raw_sample_ids(db, cutoff)
    if not sample_ids:
        return RawSampleRetentionResult(
            retention_days=retention_days,
            deleted=0,
            disabled=False,
            cutoff=cutoff,
        )

    await db.execute(delete(PeerTrafficSample).where(PeerTrafficSample.id.in_(sample_ids)))
    await db.commit()
    return RawSampleRetentionResult(
        retention_days=retention_days,
        deleted=len(sample_ids),
        disabled=False,
        cutoff=cutoff,
    )


async def _deletable_raw_sample_ids(db: AsyncSession, cutoff: datetime) -> list[str]:
    result = await db.execute(
        select(PeerTrafficSample.id)
        .distinct()
        .join(Peer, PeerTrafficSample.peer_id == Peer.id)
        .join(
            LocalAmneziawgTrafficDelta,
            (LocalAmneziawgTrafficDelta.peer_id == PeerTrafficSample.peer_id)
            & (LocalAmneziawgTrafficDelta.observed_at == PeerTrafficSample.sampled_at)
            & (LocalAmneziawgTrafficDelta.rx_delta_bytes == PeerTrafficSample.rx_bytes)
            & (LocalAmneziawgTrafficDelta.tx_delta_bytes == PeerTrafficSample.tx_bytes),
        )
        .join(
            LocalAmneziawgUserDailyTraffic,
            (LocalAmneziawgUserDailyTraffic.user_id == Peer.user_id)
            & (
                LocalAmneziawgUserDailyTraffic.day
                == func.date(LocalAmneziawgTrafficDelta.observed_at)
            ),
        )
        .join(
            LocalAmneziawgUserNodeDailyTraffic,
            (LocalAmneziawgUserNodeDailyTraffic.user_id == Peer.user_id)
            & (LocalAmneziawgUserNodeDailyTraffic.node_id == Peer.node_id)
            & (
                LocalAmneziawgUserNodeDailyTraffic.day
                == func.date(LocalAmneziawgTrafficDelta.observed_at)
            ),
        )
        .join(
            LocalAmneziawgUserLifetimeTraffic,
            LocalAmneziawgUserLifetimeTraffic.user_id == Peer.user_id,
        )
        .join(
            LocalAmneziawgUserNodeLifetimeTraffic,
            (LocalAmneziawgUserNodeLifetimeTraffic.user_id == Peer.user_id)
            & (LocalAmneziawgUserNodeLifetimeTraffic.node_id == Peer.node_id),
        )
        .where(PeerTrafficSample.sampled_at < cutoff)
    )
    return list(result.scalars().all())
