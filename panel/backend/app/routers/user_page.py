import io
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import LocalAmneziawgUserLifetimeTraffic, Node, Peer, TelegramProxySettings, User
from app.mtproxy_secret_crypto import decrypt
from app.services.local_lifecycle import local_user_blocked_reason
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
from app.services.remnawave_display import derive_remnawave_display
from app.services.telegram_proxy import build_proxy_links, select_primary_node_state

log = logging.getLogger(__name__)

router = APIRouter()
DB = Annotated[AsyncSession, Depends(get_db)]


class PublicTelegramProxy(BaseModel):
    enabled: bool
    primary_node_name: str
    tg_url: str
    https_url: str
    status: str

    model_config = ConfigDict(frozen=True)


async def _get_psk(db: AsyncSession, user_id: str, node_id: str) -> str:
    peer = (
        await db.execute(select(Peer).where(Peer.user_id == user_id, Peer.node_id == node_id))
    ).scalar_one_or_none()
    return peer.psk_key or '' if peer else ''


def _public_status(user: User, local_total: int) -> dict:
    rw = user.remnawave_user
    code = 'active'
    reason = None
    if rw is not None:
        status_map = {
            'DISABLED': ('blocked', 'disabled'),
            'LIMITED': ('limited', 'limited'),
            'EXPIRED': ('expired', 'expired'),
        }
        if rw.delete_requested_at is not None or rw.sync_status in {'missing', 'stale'}:
            code = 'blocked'
            reason = 'deleted'
        elif rw.status in status_map:
            code, reason = status_map[rw.status]
        elif (
            rw.traffic_limit_bytes > 0
            and rw.traffic_used_bytes + local_total >= rw.traffic_limit_bytes
        ):
            code = 'limited'
            reason = 'limited'
        else:
            expire_at = rw.expire_at
            if expire_at is not None:
                if expire_at.tzinfo is None:
                    expire_at = expire_at.replace(tzinfo=UTC)
                if expire_at <= datetime.now(UTC):
                    code = 'expired'
                    reason = 'expired'
    else:
        reason = local_user_blocked_reason(user, local_total)
        status_map = {
            'blocked': 'blocked',
            'limited': 'limited',
            'expired': 'expired',
        }
        if reason is not None:
            code = status_map.get(reason, 'blocked')
    return {'code': code, 'reason': reason}


async def _public_dashboard_summary(user: User, db: AsyncSession) -> dict:
    local_traffic = (
        await db.execute(
            select(LocalAmneziawgUserLifetimeTraffic).where(
                LocalAmneziawgUserLifetimeTraffic.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    local_total = local_traffic.total_bytes if local_traffic else 0
    rw = user.remnawave_user
    remote_used = rw.traffic_used_bytes if rw else 0
    total_used = remote_used + local_total
    traffic_limit = rw.traffic_limit_bytes if rw and rw.traffic_limit_bytes > 0 else None
    if rw is None and user.traffic_limit_bytes > 0:
        traffic_limit = user.traffic_limit_bytes
    updated_at = None
    if rw and rw.last_synced_at:
        updated_at = rw.last_synced_at
    if local_traffic and (updated_at is None or local_traffic.updated_at > updated_at):
        updated_at = local_traffic.updated_at
    return {
        'status': _public_status(user, local_total),
        'subscription': {
            'managed': rw is not None,
            'expire_at': rw.expire_at if rw else user.expire_at,
            'last_synced_at': rw.last_synced_at if rw else None,
        },
        'traffic': {
            'used_bytes': total_used,
            'limit_bytes': traffic_limit,
            'local_used_bytes': local_total,
            'remote_used_bytes': remote_used,
            'updated_at': local_traffic.updated_at if local_traffic else None,
        },
        'updated_at': updated_at,
    }


async def _get_public_user(db: AsyncSession, token_or_id: str) -> User | None:
    result = await db.execute(
        select(User)
        .where((User.public_token == token_or_id) | (User.id == token_or_id))
        .options(selectinload(User.remnawave_user))
    )
    return result.scalar_one_or_none()


async def _public_telegram_proxy(db: AsyncSession) -> PublicTelegramProxy | None:
    settings = await TelegramProxySettings.get_settings(db)
    payload = None
    if settings.enabled and settings.secret_encrypted is not None:
        try:
            state = await select_primary_node_state(db, settings)
        except TypeError, ValueError:
            log.warning('Stored Telegram proxy state is not valid for public links', exc_info=True)
            state = None
        if state is not None and settings.primary_node_id is not None:
            public_host = state.public_host
            public_port = state.public_port
            secret = decrypt(settings.secret_encrypted)
            node = await db.get(Node, settings.primary_node_id)
            if public_host is not None and public_port is not None and secret is not None and node:
                links = build_proxy_links(public_host, public_port, secret, settings.tls_domain)
                payload = PublicTelegramProxy(
                    enabled=True,
                    primary_node_name=node.name,
                    tg_url=links.tg_url,
                    https_url=links.t_me_url,
                    status=state.status,
                )
    return payload


def _public_user_name(user: User) -> str:
    rw = user.remnawave_user
    if rw is None:
        return user.name

    display = derive_remnawave_display(rw.description, rw.telegram_id)
    return display.display_name or user.name


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


@router.get('/pub/u/{user_id}/info')
async def pub_user_info(user_id: str, db: DB):
    user = await _get_public_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404)
    summary = await _public_dashboard_summary(user, db)
    telegram_proxy = await _public_telegram_proxy(db)
    user_name = _public_user_name(user)
    if user.is_blocked:
        return {
            'user_name': user_name,
            'blocked': True,
            'nodes': [],
            'telegram_proxy': telegram_proxy,
            **summary,
        }

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
                psk_key = await _get_psk(db, user.id, node.id)
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

    return {
        'user_name': user_name,
        'blocked': False,
        'nodes': nodes_data,
        'telegram_proxy': telegram_proxy,
        **summary,
    }


@router.get('/pub/u/{user_id}/qr/awg/{node_id}')
async def pub_awg_qr(user_id: str, node_id: str, db: DB):
    user = await _get_public_user(db, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    psk_key = await _get_psk(db, user.id, node_id)
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
    user = await _get_public_user(db, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    desc = f'{user.name} / {node.name}'
    psk_key = await _get_psk(db, user.id, node_id)
    svg = _make_vpn_qr_svg(user, node, desc, psk_key)
    if not svg:
        raise HTTPException(
            status_code=503, detail='Configuration not available or too large for QR'
        )
    return Response(svg, media_type='image/svg+xml')


@router.get('/pub/u/{user_id}/qr-chunks/vpn/{node_id}')
async def pub_vpn_qr_chunks(user_id: str, node_id: str, db: DB):
    """Returns all QR chunk SVGs for multi-part AmneziaVPN configs."""
    user = await _get_public_user(db, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not server_public_key or not server_endpoint or not private_key or not vpn_ip:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    psk_key = await _get_psk(db, user.id, node_id)
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
    user = await _get_public_user(db, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not server_public_key or not server_endpoint or not vpn_ip:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    psk_key = await _get_psk(db, user.id, node_id)
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
    user = await _get_public_user(db, user_id)
    node = await db.get(Node, node_id)
    if not user or not node:
        raise HTTPException(status_code=404)
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not private_key or not server_public_key or not server_endpoint or not vpn_ip:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    psk_key = await _get_psk(db, user.id, node_id)
    json_bytes = build_user_amnezia_config_json(user, node, f'{user.name} / {node.name}', psk_key)
    if json_bytes is None:
        raise HTTPException(status_code=503, detail='Configuration not yet available')
    filename = f'{user.name}-{node.name}.vpn'
    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
