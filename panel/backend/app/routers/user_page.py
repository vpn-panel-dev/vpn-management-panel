import io
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Node, Peer, User
from app.services.node_config import (
    QRStyle,
    build_awg_client_config,
    build_user_amnezia_config_json,
    build_user_amnezia_qr_chunks,
    build_user_amnezia_vpn_uri,
    make_amnezia_qr_svg,
    make_awg_qr_svg,
    make_qr_svg,
)

log = logging.getLogger(__name__)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


async def _get_psk(db: AsyncSession, user_id: str, node_id: str) -> str:
    peer = (
        await db.execute(select(Peer).where(Peer.user_id == user_id, Peer.node_id == node_id))
    ).scalar_one_or_none()
    return peer.psk_key or '' if peer else ''


def _make_vpn_qr_svg(user: User, node: Node, description: str, psk_key: str = '') -> bytes | None:
    try:
        return make_amnezia_qr_svg(
            user,
            node,
            description,
            psk_key,
            style=QRStyle(error='l', scale=3, border=2, dark='#111827'),
        )
    except Exception:
        return None


# ── Public endpoints (no auth — user_id UUID is the access credential) ─────────


@router.get('/pub/u/{user_id}/info')
async def pub_user_info(user_id: str, db: DB):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404)
    if user.is_blocked:
        return {'user_name': user.name, 'blocked': True, 'nodes': []}

    nodes = (await db.execute(select(Node))).scalars().all()
    nodes_data = []
    for node in nodes:
        desc = f'{user.name} / {node.name}'
        server_public_key = node.server_public_key
        server_endpoint = node.server_endpoint
        private_key = user.private_key
        vpn_ip = user.vpn_ip
        ready = bool(server_public_key and server_endpoint and private_key and vpn_ip)
        vpn_uri = None
        if server_public_key and server_endpoint and private_key and vpn_ip:
            try:
                psk_key = await _get_psk(db, user_id, node.id)
                vpn_uri = build_user_amnezia_vpn_uri(user, node, desc, psk_key)
            except Exception:
                log.warning(
                    'Failed to build VPN URI for user %s on node %s',
                    user_id,
                    node.id,
                    exc_info=True,
                )
        nodes_data.append(
            {
                'id': node.id,
                'name': node.name,
                'ready': ready,
                'vpn_uri': vpn_uri,
            }
        )

    return {'user_name': user.name, 'blocked': False, 'nodes': nodes_data}


@router.get('/pub/u/{user_id}/qr/awg/{node_id}')
async def pub_awg_qr(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    psk_key = await _get_psk(db, user_id, node_id)
    svg = make_awg_qr_svg(
        user,
        node,
        psk_key,
        style=QRStyle(error='m', scale=3, border=2, dark='#111827'),
    )
    if not svg:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    return Response(svg, media_type='image/svg+xml')


@router.get('/pub/u/{user_id}/qr/vpn/{node_id}')
async def pub_vpn_qr(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    desc = f'{user.name} / {node.name}'
    psk_key = await _get_psk(db, user_id, node_id)
    svg = _make_vpn_qr_svg(user, node, desc, psk_key)
    if not svg:
        raise HTTPException(
            status_code=503, detail='Configuration not available or too large for QR'
        )
    return Response(svg, media_type='image/svg+xml')


@router.get('/pub/u/{user_id}/qr-chunks/vpn/{node_id}')
async def pub_vpn_qr_chunks(user_id: str, node_id: str, db: DB):
    """Returns all QR chunk SVGs for multi-part AmneziaVPN configs."""
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not server_public_key or not server_endpoint or not private_key or not vpn_ip:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    psk_key = await _get_psk(db, user_id, node_id)
    desc = f'{user.name} / {node.name}'
    chunks = build_user_amnezia_qr_chunks(user, node, desc, psk_key)
    if chunks is None:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    svgs = []
    for chunk_data in chunks:
        svgs.append(
            make_qr_svg(
                chunk_data,
                QRStyle(error='l', scale=3, border=2, dark='#111827'),
            ).decode('utf-8')
        )
    return {'chunks': svgs}


@router.get('/pub/u/{user_id}/config/awg/{node_id}')
async def pub_awg_config(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not server_public_key or not server_endpoint or not vpn_ip:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    psk_key = await _get_psk(db, user_id, node_id)
    cfg = build_awg_client_config(user, node, psk_key)
    if cfg is None:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    filename = f'{user.name}-{node.name}.conf'
    return StreamingResponse(
        io.BytesIO(cfg.encode()),
        media_type='text/plain',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/pub/u/{user_id}/config/vpn/{node_id}')
async def pub_vpn_config(user_id: str, node_id: str, db: DB):
    user = await db.get(User, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not server_public_key or not server_endpoint or not vpn_ip:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    psk_key = await _get_psk(db, user_id, node_id)
    json_bytes = build_user_amnezia_config_json(user, node, f'{user.name} / {node.name}', psk_key)
    if json_bytes is None:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    filename = f'{user.name}-{node.name}.vpn'
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
