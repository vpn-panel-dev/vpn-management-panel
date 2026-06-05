from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.models import Node
from app.routers.internal_worker_parts.common import DB
from app.schemas.worker import HeartbeatResult, ProvisionResult, SyncResult
from app.services.node_config import node_snapshot
from app.services.node_sync import apply_interface_result, apply_peer_result, load_node_with_peers
from app.services.remnawave_sync import (
    enforce_remnawave_combined_limit_for_user,
    enqueue_remnawave_disable_users,
    enqueue_sync_nodes,
    now as utc_now,
    purge_confirmed_remnawave_deletes,
)

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
        node.sync_status = 'failed'
        node.sync_error = data.error or 'Worker sync failed'
        node.last_error = node.sync_error
        await db.commit()
        return {'status': 'failed'}
    synced_at = utc_now()
    node.sync_status = 'succeeded'
    node.sync_error = None
    node.last_error = None
    node.last_synced_at = synced_at
    if data.interface:
        apply_interface_result(node, data.interface)
    peers_by_public_key = {peer.user.public_key: peer for peer in peers if peer.user.public_key}
    sampled_at = utc_now()
    seen_public_keys: set[str] = set()
    limited_node_ids: set[str] = set()
    remote_disable_uuids: set[str] = set()
    for peer_result in data.peers:
        seen_public_keys.add(peer_result.public_key)
        peer = peers_by_public_key.get(peer_result.public_key)
        if not peer:
            continue
        sample = await apply_peer_result(db, peer, peer_result, sampled_at)
        if sample is not None:
            node_ids, user_uuids = await enforce_remnawave_combined_limit_for_user(db, peer.user_id)
            limited_node_ids.update(node_ids)
            remote_disable_uuids.update(user_uuids)
    for peer in peers:
        if peer.status == 'pending_delete' and peer.user.public_key not in seen_public_keys:
            peer.status = 'deleted'
    await purge_confirmed_remnawave_deletes(db)
    await db.commit()
    await enqueue_sync_nodes(db, limited_node_ids)
    await enqueue_remnawave_disable_users(db, remote_disable_uuids)
    return {'status': 'ok'}


@router.post('/nodes/{node_id}/provision-result')
async def node_provision_result(node_id: str, data: ProvisionResult, db: DB):
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    if data.ok:
        node.provision_status = 'succeeded'
        node.last_error = None
        if data.interface:
            apply_interface_result(node, data.interface)
    else:
        node.provision_status = 'failed'
        node.last_error = data.error or 'Worker provision failed'
    await db.commit()
    return {'status': node.provision_status}


@router.post('/nodes/{node_id}/heartbeat-result')
async def node_heartbeat_result(node_id: str, data: HeartbeatResult, db: DB):
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail='Node not found')
    observed_at = utc_now()
    node.last_heartbeat_at = observed_at
    node.last_seen_at = observed_at if data.ok else node.last_seen_at
    node.reachability_status = 'reachable' if data.ok else 'unreachable'
    node.health_status = 'online' if data.ok else 'offline'
    node.last_heartbeat_error = None if data.ok else data.error or 'Worker heartbeat failed'
    await db.commit()
    return {'status': node.reachability_status}
