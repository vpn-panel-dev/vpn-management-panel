from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, Field
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .schemas.remnawave import RemnawaveSyncStatus


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _public_token() -> str:
    return secrets.token_urlsafe(24)


# ── ORM Models ────────────────────────────────────────────────────────────────


class Node(Base):
    __tablename__ = 'nodes'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    health_status: Mapped[str] = mapped_column(String, default='unknown', nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reachability_status: Mapped[str] = mapped_column(String, default='unknown', nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_error: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_status: Mapped[str] = mapped_column(String, default='pending', nullable=False)
    sync_error: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provision_status: Mapped[str] = mapped_column(String, default='pending', nullable=False)

    # Set by panel on provisioning
    private_key: Mapped[str | None] = mapped_column(String, nullable=True)

    # Cached metadata — populated by sync task, used for config generation
    server_public_key: Mapped[str | None] = mapped_column(String, nullable=True)
    server_endpoint: Mapped[str | None] = mapped_column(String, nullable=True)
    listen_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jmin: Mapped[int | None] = mapped_column(Integer, nullable=True)
    jmax: Mapped[int | None] = mapped_column(Integer, nullable=True)
    s1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    s2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    s3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    s4: Mapped[int | None] = mapped_column(Integer, nullable=True)
    h1: Mapped[str | None] = mapped_column(String, nullable=True)
    h2: Mapped[str | None] = mapped_column(String, nullable=True)
    h3: Mapped[str | None] = mapped_column(String, nullable=True)
    h4: Mapped[str | None] = mapped_column(String, nullable=True)
    i1: Mapped[str | None] = mapped_column(String, nullable=True)
    i2: Mapped[str | None] = mapped_column(String, nullable=True)
    i3: Mapped[str | None] = mapped_column(String, nullable=True)
    i4: Mapped[str | None] = mapped_column(String, nullable=True)
    i5: Mapped[str | None] = mapped_column(String, nullable=True)
    mtu: Mapped[str | None] = mapped_column(String, nullable=True)

    last_error: Mapped[str | None] = mapped_column(String, nullable=True)

    peers: Mapped[list[Peer]] = relationship(
        'Peer', back_populates='node', cascade='all, delete-orphan'
    )


class User(Base):
    __tablename__ = 'users'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String, default='active', nullable=False)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    traffic_reset_policy: Mapped[str] = mapped_column(String, default='manual', nullable=False)
    traffic_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    public_token: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True, default=_public_token
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Keypair shared across all nodes
    public_key: Mapped[str | None] = mapped_column(String, nullable=True)
    private_key: Mapped[str | None] = mapped_column(String, nullable=True)
    vpn_ip: Mapped[str | None] = mapped_column(String, nullable=True)

    peers: Mapped[list[Peer]] = relationship(
        'Peer', back_populates='user', cascade='all, delete-orphan'
    )
    remnawave_user: Mapped[RemnawaveUser | None] = relationship(
        'RemnawaveUser', back_populates='user', uselist=False, cascade='all, delete-orphan'
    )


class Peer(Base):
    __tablename__ = 'peers'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    node_id: Mapped[str] = mapped_column(String, ForeignKey('nodes.id'), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey('users.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # pending → active once node acknowledges;
    # pending_delete → removed from node then deleted from DB
    status: Mapped[str] = mapped_column(String, default='pending', nullable=False)

    psk_key: Mapped[str | None] = mapped_column(String, nullable=True)

    raw_rx: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    raw_tx: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_handshake: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(String, nullable=True)

    node: Mapped[Node] = relationship('Node', back_populates='peers')
    user: Mapped[User] = relationship('User', back_populates='peers')
    samples: Mapped[list[PeerTrafficSample]] = relationship(
        'PeerTrafficSample', back_populates='peer', cascade='all, delete-orphan'
    )
    endpoint_sessions: Mapped[list[PeerEndpointSession]] = relationship(
        'PeerEndpointSession', back_populates='peer', cascade='all, delete-orphan'
    )

    __table_args__ = (UniqueConstraint('node_id', 'user_id', name='uq_peers_node_user'),)


class PeerTrafficSample(Base):
    __tablename__ = 'peer_traffic_samples'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    peer_id: Mapped[str] = mapped_column(
        String, ForeignKey('peers.id', ondelete='CASCADE'), nullable=False
    )
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    rx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    peer: Mapped[Peer] = relationship('Peer', back_populates='samples')


class PeerEndpointSession(Base):
    __tablename__ = 'peer_endpoint_sessions'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    peer_id: Mapped[str] = mapped_column(
        String, ForeignKey('peers.id', ondelete='CASCADE'), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_handshake: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    peer: Mapped[Peer] = relationship('Peer', back_populates='endpoint_sessions')


class LocalAmneziawgTrafficDelta(Base):
    __tablename__ = 'local_amneziawg_traffic_deltas'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    peer_id: Mapped[str] = mapped_column(
        String, ForeignKey('peers.id', ondelete='CASCADE'), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    source_sync_id: Mapped[str | None] = mapped_column(String, nullable=True)
    previous_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    previous_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    current_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    current_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rx_delta_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_delta_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_delta_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rx_reset_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tx_reset_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )


class LocalAmneziawgUserDailyTraffic(Base):
    __tablename__ = 'local_amneziawg_user_daily_traffic'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    __table_args__ = (UniqueConstraint('user_id', 'day'),)


class LocalAmneziawgUserNodeDailyTraffic(Base):
    __tablename__ = 'local_amneziawg_user_node_daily_traffic'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    __table_args__ = (UniqueConstraint('user_id', 'node_id', 'day'),)


class LocalAmneziawgUserLifetimeTraffic(Base):
    __tablename__ = 'local_amneziawg_user_lifetime_traffic'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class LocalAmneziawgUserNodeLifetimeTraffic(Base):
    __tablename__ = 'local_amneziawg_user_node_lifetime_traffic'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    node_id: Mapped[str] = mapped_column(
        String, ForeignKey('nodes.id', ondelete='CASCADE'), nullable=False
    )
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    __table_args__ = (UniqueConstraint('user_id', 'node_id'),)


class LocalAmneziawgTrafficSettings(Base):
    __tablename__ = 'local_amneziawg_traffic_settings'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    raw_sample_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    peer_online_threshold_seconds: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    @classmethod
    async def get_settings(cls, db):
        result = await db.execute(select(cls).order_by(cls.created_at, cls.id))
        row = result.scalars().first()
        if row is None:
            row = cls()
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return row


class AsyncOperation(Base):
    __tablename__ = 'async_operations'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RemnawaveSettings(Base):
    __tablename__ = 'remnawave_settings'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    polling_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    polling_interval_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    api_token: Mapped[str | None] = mapped_column(String, nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_status: Mapped[str | None] = mapped_column(String, nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(String, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    @classmethod
    async def get_settings(cls, db):
        result = await db.execute(select(cls))
        row = result.scalar_one_or_none()
        if row is None:
            row = cls()
            db.add(row)
            await db.commit()
            await db.refresh(row)
        return row


class RemnawaveUser(Base):
    __tablename__ = 'remnawave_users'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True
    )
    remnawave_uuid: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    remnawave_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    short_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    username: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    expire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    tag: Mapped[str | None] = mapped_column(String, nullable=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    traffic_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    traffic_limit_strategy: Mapped[str] = mapped_column(String, default='NO_RESET', nullable=False)
    traffic_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    lifetime_used_traffic_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_traffic_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_connected_node_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    hwid_device_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    external_squad_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    active_internal_squads_json: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_url_encrypted: Mapped[str | None] = mapped_column(String, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[RemnawaveSyncStatus] = mapped_column(
        String, default='synced', nullable=False
    )
    sync_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_error: Mapped[str | None] = mapped_column(String, nullable=True)
    delete_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship('User', back_populates='remnawave_user')


class RemnawaveWebhookEvent(Base):
    __tablename__ = 'remnawave_webhook_events'

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    remnawave_user_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ── Pydantic Schemas ──────────────────────────────────────────────────────────


class NodeIn(BaseModel):
    name: str
    url: str
    token: str
    server_endpoint: str | None = None
    listen_port: int | None = 51820
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


class NodeSchema(NodeIn):
    id: str
    created_at: datetime
    health_status: str = 'unknown'
    last_seen_at: datetime | None = None
    reachability_status: str = 'unknown'
    last_heartbeat_at: datetime | None = None
    last_heartbeat_error: str | None = None
    sync_status: str = 'pending'
    sync_error: str | None = None
    last_synced_at: datetime | None = None
    provision_status: str = 'pending'
    server_public_key: str | None = None
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
    last_error: str | None = None

    model_config = {'from_attributes': True}


class NodeUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    token: str | None = None
    server_endpoint: str | None = None
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


class NodeWithStatus(NodeSchema):
    online: bool
    reachable: bool
    online_peers_count: int = 0
    online_threshold_seconds: int = 180


class UserIn(BaseModel):
    name: str


class UserSchema(UserIn):
    id: str
    is_blocked: bool
    lifecycle_status: str = 'active'
    expire_at: datetime | None = None
    traffic_limit_bytes: int = 0
    traffic_reset_policy: str = 'manual'
    traffic_reset_at: datetime | None = None
    public_token: str = ''
    created_at: datetime
    public_key: str | None = None
    vpn_ip: str | None = None

    model_config = {'from_attributes': True}


class LocalUserLifecycle(BaseModel):
    source: str = 'local'
    status: str = 'active'
    expire_at: datetime | None = None
    traffic_limit_bytes: int = 0
    traffic_reset_policy: str = 'manual'
    traffic_reset_at: datetime | None = None
    blocked_reason: str | None = None


class PeerSchema(BaseModel):
    id: str
    node_id: str
    user_id: str
    status: str
    created_at: datetime
    user_name: str | None = None
    node_name: str | None = None
    vpn_ip: str | None = None
    endpoint: str | None = None
    last_handshake: datetime | None = None
    online: bool = False

    model_config = {'from_attributes': True}


class PeerBrief(BaseModel):
    node_id: str
    node_name: str
    status: str
    last_handshake: datetime | None = None
    endpoint: str | None = None
    online: bool = False


class RemnawaveUserBrief(BaseModel):
    uuid: str
    username: str
    status: str
    expire_at: datetime | None = None
    email: str | None = None
    tag: str | None = None
    traffic_used_bytes: int = 0
    traffic_limit_bytes: int = 0
    local_amneziawg_traffic_used_bytes: int = 0
    combined_traffic_used_bytes: int = 0
    blocked_reason: str | None = None
    delete_requested_at: datetime | None = None
    last_synced_at: datetime | None = None
    sync_status: RemnawaveSyncStatus = 'synced'
    sync_reason: str | None = None
    sync_error: str | None = None


class UserWithPeers(UserSchema):
    peers: list[PeerBrief] = []
    online: bool = False
    remnawave: RemnawaveUserBrief | None = None
    lifecycle: LocalUserLifecycle | None = None
    local_traffic: LocalAmneziawgUsageTotals | None = None


class TrafficPoint(BaseModel):
    day: str
    rx_bytes: int
    tx_bytes: int


class LocalAmneziawgUsageTotals(BaseModel):
    source: str = 'local_amneziawg'
    user_id: str
    rx_bytes: int = 0
    tx_bytes: int = 0
    total_bytes: int = 0
    updated_at: datetime | None = None


class LocalAmneziawgUsageNodeTotals(LocalAmneziawgUsageTotals):
    node_id: str
    node_name: str


class LocalAmneziawgNodeUsageTotals(BaseModel):
    source: str = 'local_amneziawg'
    node_id: str
    node_name: str
    rx_bytes: int = 0
    tx_bytes: int = 0
    total_bytes: int = 0
    updated_at: datetime | None = None


class LocalAmneziawgUsageDailyTotals(BaseModel):
    source: str = 'local_amneziawg'
    user_id: str
    day: date
    rx_bytes: int = 0
    tx_bytes: int = 0
    total_bytes: int = 0
    updated_at: datetime | None = None


class LocalAmneziawgUsageNodeDailyTotals(LocalAmneziawgUsageDailyTotals):
    node_id: str
    node_name: str


class LocalAmneziawgTrafficDeltaSchema(BaseModel):
    id: str
    peer_id: str
    node_id: str
    user_id: str
    observed_at: datetime
    source_sync_id: str | None = None
    previous_rx_bytes: int = 0
    previous_tx_bytes: int = 0
    current_rx_bytes: int = 0
    current_tx_bytes: int = 0
    rx_delta_bytes: int = 0
    tx_delta_bytes: int = 0
    total_delta_bytes: int = 0
    rx_reset_detected: bool = False
    tx_reset_detected: bool = False
    created_at: datetime

    model_config = {'from_attributes': True}


class LocalAmneziawgTrafficAggregateSchema(BaseModel):
    user_id: str
    node_id: str | None = None
    day: date | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    total_bytes: int = 0
    updated_at: datetime

    model_config = {'from_attributes': True}


class LocalAmneziawgTrafficSettingsSchema(BaseModel):
    id: str
    raw_sample_retention_days: int = 90
    peer_online_threshold_seconds: int = 180
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class LocalAmneziawgTrafficSettingsIn(BaseModel):
    raw_sample_retention_days: int = Field(default=90, ge=0)
    peer_online_threshold_seconds: int = Field(default=180, ge=1)


class LocalUserLifecycleUpdate(BaseModel):
    expire_at: datetime | None = None
    traffic_limit_bytes: int = Field(default=0, ge=0)
    traffic_reset_policy: str = Field(default='manual', pattern='^(manual|no_reset)$')


class RegeneratedPublicLink(BaseModel):
    public_token: str
    public_url: str


class RemnawaveSettingsIn(BaseModel):
    base_url: str | None = None
    enabled: bool = False
    polling_enabled: bool = False
    polling_interval_seconds: int = Field(default=300, ge=60)
    api_token: str | None = None
    webhook_secret: str | None = None
    subscription_url: str | None = None
    clear_api_token: bool = False
    clear_webhook_secret: bool = False


class RemnawaveSettingsSchema(BaseModel):
    id: str
    base_url: str | None = None
    enabled: bool = False
    polling_enabled: bool = False
    polling_interval_seconds: int = 300
    api_token_set: bool = False
    webhook_secret_set: bool = False
    subscription_url: str | None = None
    last_tested_at: datetime | None = None
    last_test_status: str | None = None
    last_test_error: str | None = None
    last_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}

    @classmethod
    def from_orm(cls, obj):
        data = {
            'id': obj.id,
            'base_url': obj.base_url,
            'enabled': obj.enabled,
            'polling_enabled': obj.polling_enabled,
            'polling_interval_seconds': obj.polling_interval_seconds,
            'api_token_set': obj.api_token is not None and len(obj.api_token) > 0,
            'webhook_secret_set': obj.webhook_secret is not None and len(obj.webhook_secret) > 0,
            'subscription_url': obj.subscription_url,
            'last_tested_at': obj.last_tested_at,
            'last_test_status': obj.last_test_status,
            'last_test_error': obj.last_test_error,
            'last_synced_at': obj.last_synced_at,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
        }
        return cls(**data)


class RemnawaveUserSchema(BaseModel):
    id: str
    user_id: str
    remnawave_uuid: str
    remnawave_id: int | None = None
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
    subscription_url_encrypted: str | None = None
    last_seen_at: datetime | None = None
    last_synced_at: datetime | None = None
    sync_status: RemnawaveSyncStatus = 'synced'
    sync_reason: str | None = None
    sync_error: str | None = None
    delete_requested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}


class RemnawaveWebhookEventSchema(BaseModel):
    id: str
    event_key: str
    event_type: str
    remnawave_user_uuid: str | None = None
    received_at: datetime
    processed_at: datetime | None = None

    model_config = {'from_attributes': True}
