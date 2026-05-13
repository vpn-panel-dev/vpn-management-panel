import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Node, Peer, User
from app.routers.api_parts.common import DB
from app.services.node_config import (
    QRStyle,
    build_awg_client_config,
    build_user_amnezia_qr_chunks,
    build_user_config_entries,
    build_user_configs_zip,
    make_qr_svg,
)

router = APIRouter()


async def _get_peer_psk(db: AsyncSession, user_id: str, node_id: str) -> str:
    peer = (
        await db.execute(select(Peer).where(Peer.user_id == user_id, Peer.node_id == node_id))
    ).scalar_one_or_none()
    return peer.psk_key or '' if peer else ''


@router.get('/users/{user_id}/configs')
async def api_user_configs(user_id: str, db: DB):
    """Returns per-node config texts for the user."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    if not user.private_key:
        raise HTTPException(status_code=400, detail='User has no keypair')
    vpn_ip = user.vpn_ip
    if not vpn_ip:
        raise HTTPException(status_code=400, detail='User has no VPN IP')

    nodes = (await db.execute(select(Node))).scalars().all()
    return await build_user_config_entries(
        user, nodes, lambda uid, nid: _get_peer_psk(db, uid, nid)
    )


@router.get('/users/{user_id}/configs/zip')
async def api_user_configs_zip(user_id: str, db: DB):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404)
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not vpn_ip:
        raise HTTPException(status_code=400, detail='User has no keypair or VPN IP')
    nodes = (
        (
            await db.execute(
                select(Node).where(
                    Node.server_public_key.isnot(None), Node.server_endpoint.isnot(None)
                )
            )
        )
        .scalars()
        .all()
    )
    buf = await build_user_configs_zip(user, nodes, lambda uid, nid: _get_peer_psk(db, uid, nid))
    return StreamingResponse(
        buf,
        media_type='application/zip',
        headers={'Content-Disposition': f'attachment; filename={user.name}-configs.zip'},
    )


@router.get('/users/{user_id}/configs/{node_id}')
async def api_user_config_for_node(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    if not user.private_key:
        raise HTTPException(status_code=400, detail='User has no keypair')
    vpn_ip = user.vpn_ip
    if not vpn_ip:
        raise HTTPException(status_code=400, detail='User has no VPN IP')
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    if not server_public_key or not server_endpoint:
        raise HTTPException(
            status_code=503, detail='Node metadata not yet cached — retry after sync'
        )
    psk_key = await _get_peer_psk(db, user_id, node_id)
    cfg = build_awg_client_config(user, node, psk_key)
    if cfg is None:
        raise HTTPException(
            status_code=503, detail='Node metadata not yet cached — retry after sync'
        )
    filename = f'{user.name}-{node.name}.conf'
    return StreamingResponse(
        io.BytesIO(cfg.encode()),
        media_type='text/plain',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@router.get('/users/{user_id}/qr/{node_id}')
async def api_user_qr(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    if not server_public_key or not server_endpoint:
        raise HTTPException(status_code=503, detail='Node metadata not yet cached')
    psk_key = await _get_peer_psk(db, user_id, node_id)
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not vpn_ip:
        raise HTTPException(status_code=400, detail='User has no keypair or VPN IP')
    cfg = build_awg_client_config(user, node, psk_key)
    if cfg is None:
        raise HTTPException(status_code=503, detail='Node metadata not yet cached')
    svg = make_qr_svg(
        cfg,
        QRStyle(error='m', scale=4, border=2, dark='#000000'),
    )
    return Response(svg, media_type='image/svg+xml')


@router.get('/users/{user_id}/qr-amnezia/{node_id}')
async def api_user_qr_amnezia(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    if not server_public_key or not server_endpoint:
        raise HTTPException(status_code=503, detail='Node metadata not yet cached')
    psk_key = await _get_peer_psk(db, user_id, node_id)
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not vpn_ip:
        raise HTTPException(status_code=400, detail='User has no keypair or VPN IP')
    chunks = build_user_amnezia_qr_chunks(user, node, f'{user.name} / {node.name}', psk_key)
    if chunks is None:
        raise HTTPException(status_code=503, detail='Node metadata not yet cached')
    if len(chunks) > 1:
        raise HTTPException(status_code=400, detail='Config too large for a single QR code')
    svg = make_qr_svg(
        chunks[0],
        QRStyle(error='l', scale=4, border=2, dark='#000000'),
    )
    return Response(svg, media_type='image/svg+xml')


# ── Peers (read-only from panel perspective) ──────────────────────────────────
