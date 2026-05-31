from datetime import UTC, date, datetime

from sqlalchemy import select

from app.models import (
    LocalAmneziawgTrafficDelta,
    LocalAmneziawgTrafficSettings,
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Node,
    Peer,
    User,
)


async def test_local_amneziawg_delta_stores_reset_safe_values(db):
    node, user, peer = await _create_peer(db)
    observed_at = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)
    delta = LocalAmneziawgTrafficDelta(
        peer_id=peer.id,
        node_id=node.id,
        user_id=user.id,
        observed_at=observed_at,
        source_sync_id='sync-1',
        previous_rx_bytes=5_000,
        previous_tx_bytes=1_000,
        current_rx_bytes=250,
        current_tx_bytes=1_500,
        rx_delta_bytes=250,
        tx_delta_bytes=500,
        total_delta_bytes=750,
        rx_reset_detected=True,
    )
    db.add(delta)
    await db.commit()

    result = await db.scalar(
        select(LocalAmneziawgTrafficDelta).where(LocalAmneziawgTrafficDelta.id == delta.id)
    )

    assert result is not None
    assert result.previous_rx_bytes == 5_000
    assert result.current_rx_bytes == 250
    assert result.rx_delta_bytes == 250
    assert result.tx_delta_bytes == 500
    assert result.total_delta_bytes == 750
    assert result.rx_reset_detected is True
    assert result.tx_reset_detected is False
    assert result.source_sync_id == 'sync-1'


async def test_local_amneziawg_daily_and_lifetime_aggregates_persist(db):
    node, user, _peer = await _create_peer(db)
    usage_day = date(2026, 5, 31)
    rows = [
        LocalAmneziawgUserDailyTraffic(
            user_id=user.id,
            day=usage_day,
            rx_bytes=100,
            tx_bytes=200,
            total_bytes=300,
        ),
        LocalAmneziawgUserNodeDailyTraffic(
            user_id=user.id,
            node_id=node.id,
            day=usage_day,
            rx_bytes=100,
            tx_bytes=200,
            total_bytes=300,
        ),
        LocalAmneziawgUserLifetimeTraffic(
            user_id=user.id,
            rx_bytes=1_000,
            tx_bytes=2_000,
            total_bytes=3_000,
        ),
        LocalAmneziawgUserNodeLifetimeTraffic(
            user_id=user.id,
            node_id=node.id,
            rx_bytes=1_000,
            tx_bytes=2_000,
            total_bytes=3_000,
        ),
    ]
    db.add_all(rows)
    await db.commit()

    user_daily = await db.scalar(select(LocalAmneziawgUserDailyTraffic))
    user_node_daily = await db.scalar(select(LocalAmneziawgUserNodeDailyTraffic))
    user_lifetime = await db.scalar(select(LocalAmneziawgUserLifetimeTraffic))
    user_node_lifetime = await db.scalar(select(LocalAmneziawgUserNodeLifetimeTraffic))

    assert user_daily is not None
    assert user_daily.day == usage_day
    assert user_daily.total_bytes == user_daily.rx_bytes + user_daily.tx_bytes
    assert user_node_daily is not None
    assert user_node_daily.node_id == node.id
    assert user_node_daily.total_bytes == user_node_daily.rx_bytes + user_node_daily.tx_bytes
    assert user_lifetime is not None
    assert user_lifetime.total_bytes == user_lifetime.rx_bytes + user_lifetime.tx_bytes
    assert user_node_lifetime is not None
    assert user_node_lifetime.node_id == node.id
    assert (
        user_node_lifetime.total_bytes == user_node_lifetime.rx_bytes + user_node_lifetime.tx_bytes
    )


async def test_local_amneziawg_retention_settings_default_to_90_days(db):
    settings = await LocalAmneziawgTrafficSettings.get_settings(db)

    assert settings.raw_sample_retention_days == 90

    same_settings = await LocalAmneziawgTrafficSettings.get_settings(db)
    assert same_settings.id == settings.id


async def _create_peer(db) -> tuple[Node, User, Peer]:
    node = Node(id='node-1', name='node-1', url='http://agent:8000', token='node-token')  # noqa: S106
    user = User(id='user-1', name='alice')
    peer = Peer(id='peer-1', node_id=node.id, user_id=user.id, status='active')
    db.add_all([node, user, peer])
    await db.commit()
    return node, user, peer
