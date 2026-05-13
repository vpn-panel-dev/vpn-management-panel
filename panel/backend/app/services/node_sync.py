from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Node, Peer, PeerTrafficSample
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
        if value is not None:
            setattr(node, target, value)


def apply_peer_result(peer: Peer, data: PeerSyncResult, now: datetime) -> PeerTrafficSample | None:
    if data.status in {'active', 'pending', 'pending_delete', 'deleted'}:
        peer.status = data.status
    if data.last_handshake is not None:
        peer.last_handshake = data.last_handshake
    if data.rx_bytes is None or data.tx_bytes is None:
        return None
    delta_rx = 0 if peer.raw_rx is None else max(data.rx_bytes - peer.raw_rx, 0)
    delta_tx = 0 if peer.raw_tx is None else max(data.tx_bytes - peer.raw_tx, 0)
    peer.raw_rx = data.rx_bytes
    peer.raw_tx = data.tx_bytes
    if delta_rx == 0 and delta_tx == 0:
        return None
    return PeerTrafficSample(
        peer_id=peer.id,
        sampled_at=now,
        rx_bytes=delta_rx,
        tx_bytes=delta_tx,
    )
