import base64
import dataclasses
import ipaddress
import json
import os
import struct
import zlib

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

VPN_SUBNET = os.environ.get('VPN_SUBNET', '10.8.0.0/24')


@dataclasses.dataclass(frozen=True)
class AWGClientConfig:
    private_key: str
    vpn_ip: str
    node_public_key: str
    node_endpoint: str
    public_key: str = ''
    jc: int = 4
    jmin: int = 40
    jmax: int = 70
    s1: int = 0
    s2: int = 0
    s3: int = 0
    s4: int = 0
    h1: str = '1'
    h2: str = '2'
    h3: str = '3'
    h4: str = '4'
    i1: str = ''
    i2: str = ''
    i3: str = ''
    i4: str = ''
    i5: str = ''
    psk_key: str = ''
    dns: str = '1.1.1.1'
    mtu: str = '1376'
    description: str = 'AmneziaVPN'


def generate_keypair() -> tuple[str, str]:
    """Returns (private_key_b64, public_key_b64)."""
    priv = X25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    pub_b64 = base64.b64encode(
        priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode()
    return priv_b64, pub_b64


def generate_psk() -> str:
    """Returns a random 32-byte base64-encoded WireGuard PresharedKey."""
    return base64.b64encode(os.urandom(32)).decode()


def allocate_ip(used_ips: set[str]) -> str:
    """Return the next free host IP in VPN_SUBNET not in used_ips.

    The first host (.1) is always reserved for the server gateway.
    """
    network = ipaddress.ip_network(VPN_SUBNET, strict=False)
    hosts = list(network.hosts())
    for host in hosts[1:]:  # skip .1 (server gateway)
        ip = str(host)
        if ip not in used_ips:
            return ip
    raise RuntimeError(f'VPN subnet {VPN_SUBNET} is exhausted')


def build_client_config(config: AWGClientConfig, *, dns: str | None = None) -> str:
    lines = [
        '[Interface]',
        f'Address = {config.vpn_ip}/32',
        f'DNS = {dns if dns is not None else config.dns}',
        f'PrivateKey = {config.private_key}',
        f'Jc = {config.jc}',
        f'Jmin = {config.jmin}',
        f'Jmax = {config.jmax}',
        f'S1 = {config.s1}',
        f'S2 = {config.s2}',
        f'S3 = {config.s3}',
        f'S4 = {config.s4}',
        f'H1 = {config.h1}',
        f'H2 = {config.h2}',
        f'H3 = {config.h3}',
        f'H4 = {config.h4}',
    ]
    for key, val in (
        ('I1', config.i1),
        ('I2', config.i2),
        ('I3', config.i3),
        ('I4', config.i4),
        ('I5', config.i5),
    ):
        if val:
            lines.append(f'{key} = {val}')
    lines += [
        '',
        '[Peer]',
        f'PublicKey = {config.node_public_key}',
    ]
    if config.psk_key:
        lines.append(f'PresharedKey = {config.psk_key}')
    lines += [
        'AllowedIPs = 0.0.0.0/0, ::/0',
        f'Endpoint = {config.node_endpoint}',
        'PersistentKeepalive = 25',
    ]
    return '\n'.join(lines) + '\n'


def _build_amnezia_config_json(config: AWGClientConfig, compact: bool = False) -> bytes:
    host, _, port_str = config.node_endpoint.rpartition(':')
    port = int(port_str) if port_str.isdigit() else 51820

    # The embedded config uses AmneziaVPN DNS placeholders
    conf = build_client_config(config, dns='$PRIMARY_DNS, $SECONDARY_DNS')

    # Derive subnet address (assumes /24)
    parts = config.vpn_ip.split('.')
    subnet_address = '.'.join([*parts[:3], '0'])

    last_config = {
        'H1': config.h1,
        'H2': config.h2,
        'H3': config.h3,
        'H4': config.h4,
        'I1': config.i1,
        'I2': config.i2,
        'I3': config.i3,
        'I4': config.i4,
        'I5': config.i5,
        'Jc': str(config.jc),
        'Jmax': str(config.jmax),
        'Jmin': str(config.jmin),
        'S1': str(config.s1),
        'S2': str(config.s2),
        'S3': str(config.s3),
        'S4': str(config.s4),
        'allowed_ips': ['0.0.0.0/0', '::/0'],
        'clientId': config.public_key,
        'client_ip': config.vpn_ip,
        'client_priv_key': config.private_key,
        'client_pub_key': config.public_key,
        'config': conf,
        'hostName': host,
        'mtu': config.mtu,
        'persistent_keep_alive': '25',
        'port': port,
        'psk_key': config.psk_key,
        'server_pub_key': config.node_public_key,
    }

    outer = {
        'containers': [
            {
                'awg': {
                    'H1': config.h1,
                    'H2': config.h2,
                    'H3': config.h3,
                    'H4': config.h4,
                    'I1': config.i1,
                    'I2': config.i2,
                    'I3': config.i3,
                    'I4': config.i4,
                    'I5': config.i5,
                    'Jc': str(config.jc),
                    'Jmax': str(config.jmax),
                    'Jmin': str(config.jmin),
                    'S1': str(config.s1),
                    'S2': str(config.s2),
                    'S3': str(config.s3),
                    'S4': str(config.s4),
                    'last_config': (
                        json.dumps(last_config, sort_keys=True)
                        if compact
                        else json.dumps(last_config, indent=4, sort_keys=True)
                    ),
                    'port': str(port),
                    'protocol_version': '2',
                    'subnet_address': subnet_address,
                    'transport_proto': 'udp',
                },
                'container': 'amnezia-awg2',
            }
        ],
        'defaultContainer': 'amnezia-awg2',
        'description': config.description,
        'dns1': config.dns,
        'dns2': '1.0.0.1',
        'hostName': host,
    }

    if compact:
        return json.dumps(outer, separators=(',', ':'), sort_keys=True).encode()
    return json.dumps(outer, indent=4, sort_keys=True).encode()


_AMNEZIA_QR_MAGIC = 1984
_AMNEZIA_QR_CHUNK_SIZE = 850


def build_amnezia_vpn_uri(config: AWGClientConfig) -> str:
    """Returns vpn:// deeplink for text sharing (not for QR codes)."""
    json_bytes = _build_amnezia_config_json(config)
    compressed = zlib.compress(json_bytes)
    encoded = (
        base64.urlsafe_b64encode(struct.pack('>I', len(json_bytes)) + compressed)
        .decode()
        .rstrip('=')
    )
    return f'vpn://{encoded}'


def build_amnezia_qr_chunks(config: AWGClientConfig) -> list[str]:
    """Returns list of base64 strings to encode into QR codes (AmneziaVPN binary format).

    AmneziaVPN QR format: each chunk is [magic:i16][total:u8][id:u8][data], base64-encoded.
    All values are big-endian (Qt QDataStream default).
    """
    json_bytes = _build_amnezia_config_json(config, compact=True)
    compressed = struct.pack('>I', len(json_bytes)) + zlib.compress(json_bytes)

    chunks = [
        compressed[i : i + _AMNEZIA_QR_CHUNK_SIZE]
        for i in range(0, len(compressed), _AMNEZIA_QR_CHUNK_SIZE)
    ]
    total = len(chunks)
    result = []
    for idx, chunk in enumerate(chunks):
        # QDataStream serializes QByteArray as: 4-byte big-endian length + raw bytes
        packet = struct.pack('>hBBI', _AMNEZIA_QR_MAGIC, total, idx, len(chunk)) + chunk
        result.append(base64.urlsafe_b64encode(packet).decode().rstrip('='))
    return result
