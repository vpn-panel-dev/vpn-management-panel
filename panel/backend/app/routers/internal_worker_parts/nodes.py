from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import Node
from app.routers.internal_worker_parts.common import DB
from app.schemas.worker import ProvisionResult, SyncResult
from app.services.node_config import node_snapshot
from app.services.node_sync import apply_interface_result, apply_peer_result, load_node_with_peers
from app.services.remnawave_sync import now as utc_now, purge_confirmed_remnawave_deletes

router = APIRouter()


@router.get('/sync/snapshot')
async def sync_snapshot(db: DB):
    nodes = (await db.execute(select(Node))).scalars().all()
    snapshots = []
    for node in nodes:
        _, peers = await load_node_with_peers(db, node.id)
        snapshots.append(node_snapshot(node, peers))
    return {'nodes': snapshots}


@router.get('/nodes/{node_id}/sync-snapshot')
async def node_sync_snapshot(node_id: str, db: DB):
    node, peers = await load_node_with_peers(db, node_id)
    return node_snapshot(node, peers)


@router.get('/nodes/{node_id}/provision-snapshot')
async def node_provision_snapshot(node_id: str, db: DB):
    node, peers = await load_node_with_peers(db, node_id)
    return node_snapshot(node, peers)


@router.post('/nodes/{node_id}/sync-result')
async def node_sync_result(node_id: str, data: SyncResult, db: DB):
    node, peers = await load_node_with_peers(db, node_id)
    if not data.ok:
        node.last_error = data.error or 'Worker sync failed'
        node.health_status = 'offline'
        await db.commit()
        return {'status': 'failed'}
    node.last_error = None
    node.health_status = 'online'
    node.last_seen_at = utc_now()
    if data.interface:
        apply_interface_result(node, data.interface)
    peers_by_public_key = {peer.user.public_key: peer for peer in peers if peer.user.public_key}
    sampled_at = utc_now()
    seen_public_keys: set[str] = set()
    for peer_result in data.peers:
        seen_public_keys.add(peer_result.public_key)
        peer = peers_by_public_key.get(peer_result.public_key)
        if not peer:
            continue
        sample = apply_peer_result(peer, peer_result, sampled_at)
        if sample:
            db.add(sample)
    for peer in peers:
        if peer.status == 'pending_delete' and peer.user.public_key not in seen_public_keys:
            peer.status = 'deleted'
    await purge_confirmed_remnawave_deletes(db)
    await db.commit()
    return {'status': 'ok'}


@router.post('/nodes/{node_id}/provision-result')
async def node_provision_result(node_id: str, data: ProvisionResult, db: DB):
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    if data.ok:
        node.provision_status = 'succeeded'
        node.last_error = None
        node.health_status = 'online'
        node.last_seen_at = utc_now()
        if data.interface:
            apply_interface_result(node, data.interface)
    else:
        node.provision_status = 'failed'
        node.last_error = data.error or 'Worker provision failed'
        node.health_status = 'offline'
    await db.commit()
    return {'status': node.provision_status}
