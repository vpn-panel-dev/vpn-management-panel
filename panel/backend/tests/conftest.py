import os
from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///file::memory:?cache=shared'
os.environ.setdefault('ADMIN_PASSWORD', 'testpass')
os.environ.setdefault('SECRET_KEY', 'test-secret-for-tests-only')

from app.database import Base, get_db
from app.main import app
from app.models import Node, Peer, User

app.debug = False

engine = create_async_engine(os.environ['DATABASE_URL'], echo=False)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

TEST_ADMIN_PASSWORD = 'testpass'
TEST_REMNAWAVE_SECRET_KEY = 'test-secret-32-bytes-minimum-value'
TEST_WORKER_TOKEN = 'worker-secret'


@pytest.fixture(autouse=True)
async def _setup_db():
    """Ensure clean tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


async def override_get_db() -> AsyncGenerator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture()
async def db() -> AsyncGenerator[AsyncSession]:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient]:
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def remnawave_secret_key(monkeypatch) -> str:
    monkeypatch.setenv('REMNAWAVE_SECRET_KEY', TEST_REMNAWAVE_SECRET_KEY)
    return TEST_REMNAWAVE_SECRET_KEY


@pytest.fixture()
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    resp = await client.post('/api/auth/login', json={'password': TEST_ADMIN_PASSWORD})
    assert resp.status_code == HTTPStatus.OK
    return {'Authorization': f'Bearer {resp.json()["token"]}'}


@pytest.fixture()
def worker_headers(monkeypatch) -> dict[str, str]:
    monkeypatch.setenv('WORKER_TOKEN', TEST_WORKER_TOKEN)
    return {'Authorization': f'Bearer {TEST_WORKER_TOKEN}'}


@pytest.fixture()
async def seeded_node(db: AsyncSession) -> Node:
    node = Node(id='node-1', name='node-1', url='http://agent:8000', token='node-token')  # noqa: S106
    db.add(node)
    await db.commit()
    return node


@pytest.fixture()
async def seeded_worker_state(db: AsyncSession) -> tuple[Node, User, Peer]:
    node = Node(
        id='node-1',
        name='node-1',
        url='http://agent:8000',
        token='node-token',  # noqa: S106
        private_key='node-private',
        server_public_key='old-public',
    )
    user = User(
        id='user-1',
        name='alice',
        public_key='alice-public',
        private_key='alice-private',
        vpn_ip='10.8.0.2',
    )
    peer = Peer(
        id='peer-1',
        node_id=node.id,
        user_id=user.id,
        status='pending',
        psk_key='peer-psk',
    )
    db.add_all([node, user, peer])
    await db.commit()
    return node, user, peer


@pytest.fixture()
def mock_sync_node_enqueue():
    async def _enqueue(node_id, **kwargs):
        return {'command': 'sync_node', 'target_id': node_id, **kwargs}

    with patch(
        'app.routers.internal_worker.enqueue_sync_node',
        new=AsyncMock(side_effect=_enqueue),
    ):
        yield


@pytest.fixture()
def configure_remnawave_settings():
    async def _configure(
        client: AsyncClient,
        headers: dict[str, str],
        *,
        base_url: str,
        api_token: str,
        webhook_secret: str,
    ) -> dict:
        resp = await client.put(
            '/api/remnawave/settings',
            json={
                'base_url': base_url,
                'enabled': True,
                'polling_enabled': True,
                'polling_interval_seconds': 300,
                'api_token': api_token,
                'webhook_secret': webhook_secret,
            },
            headers=headers,
        )
        assert resp.status_code == HTTPStatus.OK
        return resp.json()

    return _configure
