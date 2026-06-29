from typing import Literal, assert_never, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.models import Node, TelegramProxyNodeState, TelegramProxySettings
from app.mtproxy_secret_crypto import decrypt
from app.routers.internal_worker_parts.common import DB
from app.services.remnawave_sync import now
from app.services.telegram_proxy import normalize_public_host, normalize_public_port

type TelegramProxyResultStatus = Literal['unknown', 'disabled', 'active', 'ready', 'failed']

READY_STATUSES = frozenset({'active', 'ready'})

router = APIRouter(prefix='/telegram-proxy')


class TelegramProxyDesiredConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    secret: str | None
    port: int
    public_host: str | None
    tls_domain: str


class TelegramProxySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    node_id: str
    url: str
    token: str
    desired: TelegramProxyDesiredConfig


class TelegramProxySnapshots(BaseModel):
    model_config = ConfigDict(frozen=True)

    nodes: list[TelegramProxySnapshot]


class TelegramProxyResultIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: TelegramProxyResultStatus
    error: str | None = None
    public_host: str | None = None
    public_port: int | None = None


class TelegramProxyResultOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: TelegramProxyResultStatus
    ready: bool


def _host_from_endpoint(endpoint: str | None) -> str | None:
    if endpoint is None or endpoint == '':
        return None
    if endpoint.startswith('['):
        closing_bracket = endpoint.find(']')
        if closing_bracket == -1:
            return None
        return normalize_public_host(endpoint[: closing_bracket + 1])
    host = endpoint.split(':', maxsplit=1)[0]
    return normalize_public_host(host)


def _desired_config(settings: TelegramProxySettings, node: Node) -> TelegramProxyDesiredConfig:
    return TelegramProxyDesiredConfig(
        enabled=settings.enabled,
        secret=decrypt(settings.secret_encrypted) if settings.secret_encrypted else None,
        port=settings.port,
        public_host=_host_from_endpoint(node.server_endpoint),
        tls_domain=settings.tls_domain,
    )


def _snapshot(settings: TelegramProxySettings, node: Node) -> TelegramProxySnapshot:
    return TelegramProxySnapshot(
        node_id=node.id,
        url=node.url,
        token=node.token,
        desired=_desired_config(settings, node),
    )


def _normalize_ready_host(data: TelegramProxyResultIn) -> str:
    if data.public_host is None:
        raise HTTPException(status_code=422, detail='public_host is required for ready status')
    return normalize_public_host(data.public_host)


def _normalize_ready_port(data: TelegramProxyResultIn) -> int:
    if data.public_port is None:
        raise HTTPException(status_code=422, detail='public_port is required for ready status')
    return normalize_public_port(data.public_port)


def _apply_result(state: TelegramProxyNodeState, data: TelegramProxyResultIn) -> bool:
    observed_at = now()
    state.status = data.status
    state.last_checked_at = observed_at

    match data.status:
        case 'active' | 'ready':
            state.public_host = _normalize_ready_host(data)
            state.public_port = _normalize_ready_port(data)
            state.last_error = None
            state.last_applied_at = observed_at
            return True
        case 'failed':
            state.public_host = None
            state.public_port = None
            state.last_error = data.error or 'Worker reported failure'
            return False
        case 'disabled' | 'unknown':
            state.public_host = None
            state.public_port = None
            state.last_error = data.error
            return False
        case _ as unreachable:
            assert_never(unreachable)


@router.get('/nodes/{node_id}/snapshot')
async def get_telegram_proxy_node_snapshot(node_id: str, db: DB) -> TelegramProxySnapshot:
    node = await db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail='Node not found')
    settings = await TelegramProxySettings.get_settings(db)
    return _snapshot(settings, node)


@router.get('/snapshot')
async def get_telegram_proxy_snapshot(db: DB) -> TelegramProxySnapshots:
    settings = await TelegramProxySettings.get_settings(db)
    nodes = (await db.execute(select(Node).order_by(Node.name, Node.id))).scalars().all()
    return TelegramProxySnapshots(nodes=[_snapshot(settings, node) for node in nodes])


@router.post('/nodes/{node_id}/result')
async def report_telegram_proxy_node_result(
    node_id: str,
    data: TelegramProxyResultIn,
    db: DB,
) -> TelegramProxyResultOut:
    node = await db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail='Node not found')

    state = await db.get(TelegramProxyNodeState, node_id)
    if state is None:
        state = TelegramProxyNodeState(node_id=node.id)
        db.add(state)

    ready = _apply_result(state, data)
    await db.commit()
    return TelegramProxyResultOut(status=cast(TelegramProxyResultStatus, state.status), ready=ready)
