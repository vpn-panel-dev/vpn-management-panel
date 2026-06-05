from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.crypto import generate_keypair
from app.models import (
    LocalAmneziawgNodeUsageTotals,
    LocalAmneziawgUserNodeLifetimeTraffic,
    Node,
    NodeIn,
    NodeSchema,
    NodeUpdate,
    NodeWithStatus,
    Peer,
    PeerSchema,
)
from app.routers.api_parts.common import DB
from app.services.online import is_peer_online, online_threshold_seconds
from app.services.operations import enqueue_operation, new_operation, operation_response
from app.services.users import create_pending_peers_for_node

router = APIRouter()


@router.get('/nodes', response_model=list[NodeWithStatus])
async def api_list_nodes(db: DB):
    threshold_seconds = await online_threshold_seconds(db)
    nodes = (await db.execute(select(Node).options(selectinload(Node.peers)))).scalars().all()
    return [
        NodeWithStatus(
            **NodeSchema.model_validate(node).model_dump(),
            online=node.reachability_status == 'reachable',
            reachable=node.reachability_status == 'reachable',
            online_peers_count=sum(
                1 for peer in node.peers if is_peer_online(peer, threshold_seconds)
            ),
            online_threshold_seconds=threshold_seconds,
        )
        for node in nodes
    ]


@router.post('/nodes', response_model=NodeSchema, status_code=201)
async def api_add_node(data: NodeIn, db: DB):
    priv, pub = generate_keypair()
    node = Node(
        **data.model_dump(),
        private_key=priv,
        server_public_key=pub,
        provision_status='pending',
    )
    db.add(node)
    await db.flush()

    await create_pending_peers_for_node(db, node)
    await db.commit()
    await db.refresh(node)

    operation = new_operation('provision_node', 'node', node.id)
    from app.routers import api as api_router

    await enqueue_operation(db, operation, api_router.enqueue_provision_node, node.id)
    await db.refresh(node)

    return node


@router.post('/nodes/{node_id}/provision', status_code=202)
async def api_provision_node(node_id: str, db: DB):
    """Re-send interface config to the node agent (use after node restart or first boot)."""
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    if not node.private_key:
        node.private_key, node.server_public_key = generate_keypair()
    node.provision_status = 'pending'
    node.last_error = None
    await db.commit()
    await db.refresh(node)
    operation = new_operation('provision_node', 'node', node.id)
    from app.routers import api as api_router

    await enqueue_operation(db, operation, api_router.enqueue_provision_node, node.id)
    return operation_response(operation)


@router.patch('/nodes/{node_id}', response_model=NodeSchema)
async def api_update_node(node_id: str, data: NodeUpdate, db: DB):
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    node.provision_status = 'pending'
    await db.commit()
    await db.refresh(node)
    operation = new_operation('provision_node', 'node', node.id)
    from app.routers import api as api_router

    await enqueue_operation(db, operation, api_router.enqueue_provision_node, node.id)
    await db.refresh(node)
    return node


@router.delete('/nodes/{node_id}', status_code=204)
async def api_delete_node(node_id: str, db: DB):
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    await db.delete(node)
    await db.commit()


# ── Users ─────────────────────────────────────────────────────────────────────


@router.get('/nodes/{node_id}/peers', response_model=list[PeerSchema])
async def api_node_peers(node_id: str, db: DB):
    threshold_seconds = await online_threshold_seconds(db)
    rows = (
        (
            await db.execute(
                select(Peer)
                .where(Peer.node_id == node_id)
                .options(selectinload(Peer.user), selectinload(Peer.node))
            )
        )
        .scalars()
        .all()
    )
    result = []
    for p in rows:
        s = PeerSchema.model_validate(p)
        s.user_name = p.user.name
        s.node_name = p.node.name
        s.vpn_ip = p.user.vpn_ip
        s.online = is_peer_online(p, threshold_seconds)
        result.append(s)
    return result


# ── Traffic stats ─────────────────────────────────────────────────────────────


@router.get('/nodes/{node_id}/local-traffic', response_model=LocalAmneziawgNodeUsageTotals)
async def api_node_local_traffic(node_id: str, db: DB):
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')

    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(LocalAmneziawgUserNodeLifetimeTraffic.rx_bytes), 0),
                func.coalesce(func.sum(LocalAmneziawgUserNodeLifetimeTraffic.tx_bytes), 0),
                func.coalesce(func.sum(LocalAmneziawgUserNodeLifetimeTraffic.total_bytes), 0),
                func.max(LocalAmneziawgUserNodeLifetimeTraffic.updated_at),
            ).where(LocalAmneziawgUserNodeLifetimeTraffic.node_id == node_id)
        )
    ).one()
    rx_bytes, tx_bytes, total_bytes, updated_at = row
    return LocalAmneziawgNodeUsageTotals(
        node_id=node.id,
        node_name=node.name,
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
        total_bytes=total_bytes,
        updated_at=updated_at,
    )
