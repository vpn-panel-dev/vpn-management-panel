import io
import zipfile
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

import segno

from app.crypto import (
    AWGClientConfig,
    _build_amnezia_config_json,
    build_amnezia_qr_chunks,
    build_amnezia_vpn_uri,
    build_client_config,
)
from app.models import Node, Peer, User

_NODE_VPN_ADDRESS = '10.8.0.1/24'
_POST_UP = (
    'iptables -t nat -A POSTROUTING -s 10.8.0.0/24 -j MASQUERADE; '
    'iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT'
)
_POST_DOWN = (
    'iptables -t nat -D POSTROUTING -s 10.8.0.0/24 -j MASQUERADE; '
    'iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT'
)


@dataclass(frozen=True)
class QRStyle:
    error: str
    scale: int
    border: int
    dark: str
    light: str = '#ffffff'


def node_kwargs(node: Node) -> dict[str, Any]:
    return {
        'jc': node.jc or 4,
        'jmin': node.jmin or 40,
        'jmax': node.jmax or 70,
        's1': node.s1 or 0,
        's2': node.s2 or 0,
        's3': node.s3 or 0,
        's4': node.s4 or 0,
        'h1': node.h1 or '1',
        'h2': node.h2 or '2',
        'h3': node.h3 or '3',
        'h4': node.h4 or '4',
        'i1': node.i1 or '',
        'i2': node.i2 or '',
        'i3': node.i3 or '',
        'i4': node.i4 or '',
        'i5': node.i5 or '',
    }


def node_mtu(node: Node) -> str:
    return node.mtu or '1376'


def build_awg_client_config(user: User, node: Node, psk_key: str = '') -> str | None:
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not server_public_key or not server_endpoint or not private_key or not vpn_ip:
        return None
    return build_client_config(
        AWGClientConfig(
            private_key=private_key,
            vpn_ip=vpn_ip,
            node_public_key=server_public_key,
            node_endpoint=server_endpoint,
            psk_key=psk_key,
            **node_kwargs(node),
        )
    )


def build_amnezia_client_config(
    user: User,
    node: Node,
    description: str,
    psk_key: str = '',
    *,
    dns: str = '1.1.1.1',
) -> AWGClientConfig | None:
    server_public_key = node.server_public_key
    server_endpoint = node.server_endpoint
    private_key = user.private_key
    vpn_ip = user.vpn_ip
    if not server_public_key or not server_endpoint or not private_key or not vpn_ip:
        return None
    return AWGClientConfig(
        private_key=private_key,
        public_key=user.public_key or '',
        vpn_ip=vpn_ip,
        node_public_key=server_public_key,
        node_endpoint=server_endpoint,
        dns=dns,
        description=description,
        psk_key=psk_key,
        mtu=node_mtu(node),
        **node_kwargs(node),
    )


def build_user_amnezia_qr_chunks(
    user: User,
    node: Node,
    description: str,
    psk_key: str = '',
) -> list[str] | None:
    config = build_amnezia_client_config(user, node, description, psk_key)
    return build_amnezia_qr_chunks(config) if config else None


def build_user_amnezia_vpn_uri(
    user: User,
    node: Node,
    description: str,
    psk_key: str = '',
) -> str | None:
    config = build_amnezia_client_config(user, node, description, psk_key)
    return build_amnezia_vpn_uri(config) if config else None


def build_user_amnezia_config_json(
    user: User,
    node: Node,
    description: str,
    psk_key: str = '',
) -> bytes | None:
    config = build_amnezia_client_config(user, node, description, psk_key, dns='1.1.1.1')
    return _build_amnezia_config_json(config) if config else None


def make_qr_svg(
    data: str,
    style: QRStyle,
) -> bytes:
    buf = io.BytesIO()
    segno.make(data, error=style.error).save(
        buf,
        kind='svg',
        scale=style.scale,
        border=style.border,
        svgclass=None,
        lineclass=None,
        dark=style.dark,
        light=style.light,
    )
    return buf.getvalue()


def make_awg_qr_svg(
    user: User,
    node: Node,
    psk_key: str = '',
    *,
    style: QRStyle,
) -> bytes | None:
    config = build_awg_client_config(user, node, psk_key)
    if not config:
        return None
    return make_qr_svg(config, style)


def make_amnezia_qr_svg(
    user: User,
    node: Node,
    description: str,
    psk_key: str = '',
    *,
    style: QRStyle,
) -> bytes | None:
    chunks = build_user_amnezia_qr_chunks(user, node, description, psk_key)
    if not chunks or len(chunks) > 1:
        return None
    return make_qr_svg(chunks[0], style)


async def build_user_config_entries(
    user: User,
    nodes: Iterable[Node],
    get_peer_psk: Callable[[str, str], Awaitable[str]],
) -> list[dict[str, str | None]]:
    result: list[dict[str, str | None]] = []
    for node in nodes:
        if not node.server_public_key or not node.server_endpoint:
            result.append(
                {
                    'node_id': node.id,
                    'node_name': node.name,
                    'config': None,
                    'reason': 'node metadata not yet cached',
                }
            )
            continue
        config = build_awg_client_config(user, node, await get_peer_psk(user.id, node.id))
        result.append({'node_id': node.id, 'node_name': node.name, 'config': config})
    return result


async def build_user_configs_zip(
    user: User,
    nodes: Iterable[Node],
    get_peer_psk: Callable[[str, str], Awaitable[str]],
) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for node in nodes:
            if not node.server_public_key or not node.server_endpoint:
                continue
            config = build_awg_client_config(user, node, await get_peer_psk(user.id, node.id))
            if config:
                zf.writestr(f'{user.name}-{node.name}.conf', config)
    buf.seek(0)
    return buf


def node_interface(node: Node) -> dict[str, Any]:
    return {
        'private_key': node.private_key,
        'address': _NODE_VPN_ADDRESS,
        'listen_port': node.listen_port or 51820,
        **node_kwargs(node),
        'mtu': node_mtu(node),
        'post_up': _POST_UP,
        'post_down': _POST_DOWN,
    }


def peer_payload(peer: Peer) -> dict[str, Any] | None:
    user = peer.user
    if not user.public_key or not user.vpn_ip:
        return None
    return {
        'peer_id': peer.id,
        'user_id': user.id,
        'user_name': user.name,
        'public_key': user.public_key,
        'allowed_ip': user.vpn_ip,
        'psk_key': peer.psk_key or '',
        'status': peer.status,
        'is_blocked': user.is_blocked,
    }


def node_snapshot(node: Node, peers: list[Peer]) -> dict[str, Any]:
    return {
        'id': node.id,
        'name': node.name,
        'url': node.url,
        'token': node.token,
        'provision_status': node.provision_status,
        'interface': node_interface(node),
        'peers': [payload for peer in peers if (payload := peer_payload(peer))],
    }
