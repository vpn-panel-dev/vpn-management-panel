from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    LocalAmneziawgTrafficDelta,
    LocalAmneziawgUserDailyTraffic,
    LocalAmneziawgUserLifetimeTraffic,
    LocalAmneziawgUserNodeDailyTraffic,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Node,
    Peer,
    PeerEndpointSession,
    PeerTrafficSample,
)
from app.schemas.worker import InterfaceResult, PeerSyncResult


async def load_node_with_peers(db: AsyncSession, node_id: str) -> tuple[Node, list[Peer]]:
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    peers = (
        (
            await db.execute(
                select(Peer).where(Peer.node_id == node.id).options(selectinload(Peer.user))
            )
        )
        .scalars()
        .all()
    )
    return node, list(peers)


def apply_interface_result(node: Node, data: InterfaceResult) -> None:
    field_map = {
        'public_key': 'server_public_key',
        'endpoint': 'server_endpoint',
        'listen_port': 'listen_port',
        'jc': 'jc',
        'jmin': 'jmin',
        'jmax': 'jmax',
        's1': 's1',
        's2': 's2',
        's3': 's3',
        's4': 's4',
        'h1': 'h1',
        'h2': 'h2',
        'h3': 'h3',
        'h4': 'h4',
        'i1': 'i1',
        'i2': 'i2',
        'i3': 'i3',
        'i4': 'i4',
        'i5': 'i5',
        'mtu': 'mtu',
    }
    for source, target in field_map.items():
        value = getattr(data, source)
        if value is not None and getattr(node, target) != value:
            setattr(node, target, value)


async def apply_peer_result(
    db: AsyncSession, peer: Peer, data: PeerSyncResult, now: datetime
) -> PeerTrafficSample | None:
    if (
        data.status in {'active', 'pending', 'pending_delete', 'deleted'}
        and peer.status != data.status
    ):
        peer.status = data.status
    if 'endpoint' in data.model_fields_set and peer.endpoint != data.endpoint:
        peer.endpoint = data.endpoint
    if data.last_handshake is not None and peer.last_handshake != data.last_handshake:
        peer.last_handshake = data.last_handshake
    await _apply_peer_endpoint_session(db, peer, data, now)
    if data.rx_bytes is None or data.tx_bytes is None:
        return None

    previous_rx = peer.raw_rx or 0
    previous_tx = peer.raw_tx or 0
    rx_reset_detected = peer.raw_rx is not None and data.rx_bytes < peer.raw_rx
    tx_reset_detected = peer.raw_tx is not None and data.tx_bytes < peer.raw_tx
    delta_rx = _counter_delta(peer.raw_rx, data.rx_bytes)
    delta_tx = _counter_delta(peer.raw_tx, data.tx_bytes)
    if peer.raw_rx != data.rx_bytes:
        peer.raw_rx = data.rx_bytes
    if peer.raw_tx != data.tx_bytes:
        peer.raw_tx = data.tx_bytes
    if delta_rx == 0 and delta_tx == 0:
        return None

    sample = PeerTrafficSample(
        peer_id=peer.id,
        sampled_at=now,
        rx_bytes=delta_rx,
        tx_bytes=delta_tx,
    )
    db.add(sample)
    db.add(
        LocalAmneziawgTrafficDelta(
            peer_id=peer.id,
            node_id=peer.node_id,
            user_id=peer.user_id,
            observed_at=now,
            previous_rx_bytes=previous_rx,
            previous_tx_bytes=previous_tx,
            current_rx_bytes=data.rx_bytes,
            current_tx_bytes=data.tx_bytes,
            rx_delta_bytes=delta_rx,
            tx_delta_bytes=delta_tx,
            total_delta_bytes=delta_rx + delta_tx,
            rx_reset_detected=rx_reset_detected,
            tx_reset_detected=tx_reset_detected,
        )
    )
    await _apply_local_traffic_aggregates(db, peer, now, delta_rx, delta_tx)
    return sample


async def _apply_peer_endpoint_session(
    db: AsyncSession, peer: Peer, data: PeerSyncResult, observed_at: datetime
) -> None:
    if not data.endpoint:
        return

    session = await db.scalar(
        select(PeerEndpointSession)
        .where(PeerEndpointSession.peer_id == peer.id)
        .order_by(PeerEndpointSession.last_seen_at.desc())
    )
    if session is None or session.endpoint != data.endpoint:
        db.add(
            PeerEndpointSession(
                peer_id=peer.id,
                node_id=peer.node_id,
                user_id=peer.user_id,
                endpoint=data.endpoint,
                first_seen_at=observed_at,
                last_seen_at=observed_at,
                last_handshake=data.last_handshake,
            )
        )
        return

    if data.last_handshake is not None and session.last_handshake != data.last_handshake:
        session.last_seen_at = observed_at
        session.last_handshake = data.last_handshake


def _counter_delta(previous: int | None, current: int) -> int:
    if previous is None:
        return 0
    if current < previous:
        return current
    return current - previous


async def _apply_local_traffic_aggregates(
    db: AsyncSession, peer: Peer, observed_at: datetime, rx_delta: int, tx_delta: int
) -> None:
    total_delta = rx_delta + tx_delta
    usage_day = observed_at.date()
    await _increase_aggregate(
        db,
        LocalAmneziawgUserDailyTraffic,
        {'user_id': peer.user_id, 'day': usage_day},
        (rx_delta, tx_delta, total_delta),
        observed_at,
    )
    await _increase_aggregate(
        db,
        LocalAmneziawgUserNodeDailyTraffic,
        {'user_id': peer.user_id, 'node_id': peer.node_id, 'day': usage_day},
        (rx_delta, tx_delta, total_delta),
        observed_at,
    )
    await _increase_aggregate(
        db,
        LocalAmneziawgUserLifetimeTraffic,
        {'user_id': peer.user_id},
        (rx_delta, tx_delta, total_delta),
        observed_at,
    )
    await _increase_aggregate(
        db,
        LocalAmneziawgUserNodeLifetimeTraffic,
        {'user_id': peer.user_id, 'node_id': peer.node_id},
        (rx_delta, tx_delta, total_delta),
        observed_at,
    )


async def _increase_aggregate(
    db: AsyncSession,
    model: type[Any],
    identity: dict[str, object],
    increment: tuple[int, int, int],
    observed_at: datetime,
) -> None:
    rx_delta, tx_delta, total_delta = increment
    statement = select(model)
    for column_name, value in identity.items():
        statement = statement.where(getattr(model, column_name) == value)

    aggregate = (await db.execute(statement)).scalar_one_or_none()
    if aggregate is None:
        aggregate = model(
            **identity,
            rx_bytes=rx_delta,
            tx_bytes=tx_delta,
            total_bytes=total_delta,
            updated_at=observed_at,
        )
        db.add(aggregate)
        return

    aggregate.rx_bytes += rx_delta
    aggregate.tx_bytes += tx_delta
    aggregate.total_bytes += total_delta
    aggregate.updated_at = observed_at
