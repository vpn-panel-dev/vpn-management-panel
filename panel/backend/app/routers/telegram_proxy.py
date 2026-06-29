from datetime import UTC, datetime
from typing import Annotated

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.job_commands import (
    enqueue_telegram_proxy_apply_node,
    enqueue_telegram_proxy_disable_node,
)
from app.models import (
    Node,
    TelegramProxyNodeState,
    TelegramProxySettings,
    TelegramProxySettingsSchema,
)
from app.mtproxy_secret_crypto import decrypt, encrypt
from app.routers.auth import require_auth
from app.services.operations import enqueue_operation, new_operation, operation_response
from app.services.telegram_proxy import (
    TelegramProxyLinks,
    build_proxy_links,
    generate_proxy_secret,
    normalize_public_host,
    select_primary_node_state,
    validate_proxy_secret,
)

router = APIRouter(prefix='/api/telegram-proxy', dependencies=[Depends(require_auth)])
DB = Annotated[AsyncSession, Depends(get_db)]


class TelegramProxySettingsIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool
    port: int = Field(ge=1, le=65535)
    primary_node_id: str | None = None
    public_host: str | None = None
    tls_domain: str = 'cloudsyncpro.net'
    secret: str | None = None

    @field_validator('public_host')
    @classmethod
    def normalize_host(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_public_host(value)

    @field_validator('tls_domain')
    @classmethod
    def normalize_tls_domain(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == '':
            raise ValueError('telegram proxy tls domain is required')
        return normalized

    @field_validator('secret')
    @classmethod
    def normalize_secret(cls, value: str | None) -> str | None:
        if value is None or value == '':
            return None
        return validate_proxy_secret(value)


class TelegramProxyLinksOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tg_url: str
    t_me_url: str


class TelegramProxySettingsOut(TelegramProxySettingsSchema):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    links: TelegramProxyLinksOut | None = None


class TelegramProxyNodeStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    node_id: str
    status: str
    public_host: str | None
    public_port: int | None
    last_applied_at: datetime | None
    last_checked_at: datetime | None
    last_error: str | None


class TelegramProxyStatusOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    settings: TelegramProxySettingsOut
    primary_node_state: TelegramProxyNodeStateOut | None
    links: TelegramProxyLinksOut | None


def _links_out(links: TelegramProxyLinks) -> TelegramProxyLinksOut:
    return TelegramProxyLinksOut(tg_url=links.tg_url, t_me_url=links.t_me_url)


async def _response_links(
    db: AsyncSession,
    settings: TelegramProxySettings,
) -> TelegramProxyLinksOut | None:
    if not settings.enabled or not settings.secret_encrypted:
        return None

    primary_state = await select_primary_node_state(db, settings)
    if primary_state is None:
        return None
    public_host = primary_state.public_host
    public_port = primary_state.public_port
    if public_host is None or public_port is None:
        return None

    try:
        secret = decrypt(settings.secret_encrypted)
    except InvalidToken:
        return None
    if secret is None:
        return None

    links = build_proxy_links(public_host, public_port, secret, settings.tls_domain)
    return _links_out(links)


async def _settings_out(
    db: AsyncSession,
    settings: TelegramProxySettings,
) -> TelegramProxySettingsOut:
    data = TelegramProxySettingsSchema.from_orm(settings).model_dump()
    return TelegramProxySettingsOut(**data, links=await _response_links(db, settings))


async def _primary_node(db: AsyncSession, settings: TelegramProxySettings) -> Node:
    if settings.primary_node_id is None:
        raise HTTPException(status_code=409, detail='Telegram proxy primary node is not configured')
    node = await db.get(Node, settings.primary_node_id)
    if node is None:
        raise HTTPException(status_code=404, detail='Telegram proxy primary node not found')
    return node


async def _enqueue_apply_operation(db: AsyncSession, node: Node) -> dict[str, str]:
    operation = new_operation('telegram_proxy_apply_node', 'node', node.id)
    await enqueue_operation(db, operation, enqueue_telegram_proxy_apply_node, node.id)
    return operation_response(operation)


@router.get('/settings', response_model=TelegramProxySettingsOut)
async def get_telegram_proxy_settings(db: DB) -> TelegramProxySettingsOut:
    settings = await TelegramProxySettings.get_settings(db)
    return await _settings_out(db, settings)


@router.put('/settings', response_model=TelegramProxySettingsOut)
async def update_telegram_proxy_settings(
    data: TelegramProxySettingsIn,
    db: DB,
) -> TelegramProxySettingsOut:
    if data.primary_node_id is not None and await db.get(Node, data.primary_node_id) is None:
        raise HTTPException(status_code=404, detail='Primary node not found')

    settings = await TelegramProxySettings.get_settings(db)
    settings.enabled = data.enabled
    settings.port = data.port
    settings.primary_node_id = data.primary_node_id
    settings.tls_domain = data.tls_domain
    if data.secret is not None:
        settings.secret_encrypted = encrypt(data.secret)
    await db.commit()
    await db.refresh(settings)
    return await _settings_out(db, settings)


@router.post('/apply', status_code=202)
async def apply_telegram_proxy(db: DB) -> dict[str, str]:
    settings = await TelegramProxySettings.get_settings(db)
    if not settings.enabled:
        raise HTTPException(status_code=409, detail='Telegram proxy is disabled')
    if not settings.secret_encrypted:
        raise HTTPException(status_code=409, detail='Telegram proxy secret is not configured')
    node = await _primary_node(db, settings)
    return await _enqueue_apply_operation(db, node)


@router.post('/disable', status_code=202)
async def disable_telegram_proxy(db: DB) -> dict[str, str]:
    settings = await TelegramProxySettings.get_settings(db)
    node = await _primary_node(db, settings)
    settings.enabled = False
    await db.commit()
    operation = new_operation('telegram_proxy_disable_node', 'node', node.id)
    await enqueue_operation(db, operation, enqueue_telegram_proxy_disable_node, node.id)
    return operation_response(operation)


@router.post('/rotate-secret', status_code=202)
async def rotate_telegram_proxy_secret(db: DB) -> dict[str, str]:
    settings = await TelegramProxySettings.get_settings(db)
    node = await _primary_node(db, settings)
    settings.secret_encrypted = encrypt(generate_proxy_secret())
    settings.last_rotation_at = datetime.now(UTC)
    settings.last_rotation_reason = 'manual'
    settings.last_rotation_error = None
    await db.commit()
    return await _enqueue_apply_operation(db, node)


@router.get('/status', response_model=TelegramProxyStatusOut)
async def get_telegram_proxy_status(db: DB) -> TelegramProxyStatusOut:
    settings = await TelegramProxySettings.get_settings(db)
    primary_state = None
    if settings.primary_node_id is not None:
        primary_state = await db.get(TelegramProxyNodeState, settings.primary_node_id)
    links = await _response_links(db, settings)
    return TelegramProxyStatusOut(
        settings=await _settings_out(db, settings),
        primary_node_state=(
            TelegramProxyNodeStateOut.model_validate(primary_state)
            if primary_state is not None
            else None
        ),
        links=links,
    )
