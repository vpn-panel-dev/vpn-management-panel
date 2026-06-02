from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OperationResult(BaseModel):
    result: dict[str, Any] | None = None
    error: str | None = None


class InterfaceResult(BaseModel):
    public_key: str | None = None
    endpoint: str | None = None
    listen_port: int | None = None
    jc: int | None = None
    jmin: int | None = None
    jmax: int | None = None
    s1: int | None = None
    s2: int | None = None
    s3: int | None = None
    s4: int | None = None
    h1: str | None = None
    h2: str | None = None
    h3: str | None = None
    h4: str | None = None
    i1: str | None = None
    i2: str | None = None
    i3: str | None = None
    i4: str | None = None
    i5: str | None = None
    mtu: str | None = None


class PeerSyncResult(BaseModel):
    public_key: str
    status: str | None = None
    endpoint: str | None = None
    rx_bytes: int | None = Field(default=None, ge=0)
    tx_bytes: int | None = Field(default=None, ge=0)
    last_handshake: datetime | None = None


class SyncResult(BaseModel):
    ok: bool = True
    error: str | None = None
    interface: InterfaceResult | None = None
    peers: list[PeerSyncResult] = []


class ProvisionResult(BaseModel):
    ok: bool = True
    error: str | None = None
    interface: InterfaceResult | None = None


class RemnawaveReconcileCompleteIn(BaseModel):
    seen_uuids: list[str] = Field(default_factory=list)


class RemnawaveUserIn(BaseModel):
    uuid: str
    id: int | None = None
    short_uuid: str | None = None
    username: str
    status: str
    expire_at: datetime | None = None
    email: str | None = None
    tag: str | None = None
    telegram_id: int | None = None
    description: str | None = None
    traffic_limit_bytes: int = 0
    traffic_limit_strategy: str = 'NO_RESET'
    traffic_used_bytes: int = 0
    lifetime_used_traffic_bytes: int = 0
    last_traffic_reset_at: datetime | None = None
    online_at: datetime | None = None
    first_connected_at: datetime | None = None
    last_connected_node_uuid: str | None = None
    hwid_device_limit: int | None = None
    external_squad_uuid: str | None = None
    active_internal_squads_json: str | None = None
    subscription_url: str | None = None
