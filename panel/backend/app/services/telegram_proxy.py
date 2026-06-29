import re
import secrets
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramProxyNodeState, TelegramProxySettings

_NORMAL_SECRET_RE = re.compile(r'^[0-9a-f]{32}$')
_DD_SECRET_RE = re.compile(r'^dd[0-9a-f]{32}$')
_FAKE_TLS_DOMAIN = 'cloudsyncpro.net'
_FAKE_TLS_DOMAIN_HEX = _FAKE_TLS_DOMAIN.encode().hex()
_READY_STATUSES = frozenset({'active', 'ready'})
_MIN_PUBLIC_PORT = 1
_MAX_PUBLIC_PORT = 65535


@dataclass(frozen=True, slots=True)
class TelegramProxyLinks:
    tg_url: str
    t_me_url: str


def generate_proxy_secret(*, dd_prefixed: bool = False) -> str:
    secret = secrets.token_hex(16)
    if dd_prefixed:
        return f'dd{secret}'
    return secret


def validate_proxy_secret(secret: str) -> str:
    normalized = secret.lower()
    if _NORMAL_SECRET_RE.fullmatch(normalized) or _DD_SECRET_RE.fullmatch(normalized):
        return normalized
    raise ValueError('telegram proxy secret must be 32 hex characters or dd plus 32 hex characters')


def format_proxy_link_secret(secret: str, tls_domain: str) -> str:
    normalized = validate_proxy_secret(secret)
    base_secret = normalized[2:] if normalized.startswith('dd') else normalized
    return f'ee{base_secret}{tls_domain.encode().hex()}'


def normalize_public_host(host: str) -> str:
    if host != host.strip():
        raise ValueError('telegram proxy public host must not include surrounding whitespace')
    if host == '':
        raise ValueError('telegram proxy public host is required')
    if '://' in host or '/' in host or '?' in host or '#' in host or '@' in host:
        raise ValueError('telegram proxy public host must be a host, not a URL')
    if ':' in host and not (host.startswith('[') and host.endswith(']')):
        raise ValueError('telegram proxy public host must not include a port')
    return host.lower()


def normalize_public_port(port: object) -> int:
    if isinstance(port, bool) or not isinstance(port, int):
        raise TypeError('telegram proxy public port must be an integer')
    if _MIN_PUBLIC_PORT <= port <= _MAX_PUBLIC_PORT:
        return port
    raise ValueError('telegram proxy public port must be between 1 and 65535')


def build_proxy_links(host: str, port: object, secret: str, tls_domain: str) -> TelegramProxyLinks:
    query = urlencode(
        {
            'server': normalize_public_host(host),
            'port': str(normalize_public_port(port)),
            'secret': format_proxy_link_secret(secret, tls_domain),
        },
        quote_via=quote,
    )
    return TelegramProxyLinks(
        tg_url=f'tg://proxy?{query}',
        t_me_url=f'https://t.me/proxy?{query}',
    )


async def select_primary_node_state(
    db: AsyncSession,
    settings: TelegramProxySettings,
) -> TelegramProxyNodeState | None:
    if settings.primary_node_id is None:
        return None

    state = await db.scalar(
        select(TelegramProxyNodeState).where(
            TelegramProxyNodeState.node_id == settings.primary_node_id
        )
    )
    if state is None:
        return None
    if state.status not in _READY_STATUSES:
        return None
    if state.public_host is None or state.public_port is None:
        return None

    normalize_public_host(state.public_host)
    normalize_public_port(state.public_port)
    return state
