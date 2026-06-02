from datetime import UTC

from sqlalchemy import select

from app.models import AsyncOperation, Node, NodeIn, NodeSchema, PeerSchema, UserIn, UserSchema


def test_node_in_validation():
    data = NodeIn(name='test-node', url='http://node:8000', token='secret')  # noqa: S106
    assert data.name == 'test-node'
    assert data.url == 'http://node:8000'
    assert data.listen_port == 51820


def test_node_schema_from_attributes():
    import uuid
    from datetime import datetime

    node_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    schema = NodeSchema(
        id=node_id,
        name='test',
        url='http://node:8000',
        token='secret',  # noqa: S106
        created_at=now,
        listen_port=51820,
    )
    assert schema.id == node_id
    assert schema.listen_port == 51820


def test_user_in_validation():
    data = UserIn(name='test-user')
    assert data.name == 'test-user'


def test_user_schema_from_attributes():
    import uuid
    from datetime import datetime

    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    schema = UserSchema(
        id=user_id,
        name='test-user',
        is_blocked=False,
        created_at=now,
    )
    assert schema.id == user_id
    assert not schema.is_blocked


def test_peer_schema():
    import uuid
    from datetime import datetime

    now = datetime.now(UTC)
    schema = PeerSchema(
        id=str(uuid.uuid4()),
        node_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        status='active',
        created_at=now,
        user_name='alice',
        node_name='node-1',
        vpn_ip='10.8.0.2',
        endpoint='203.0.113.10:54321',
        last_handshake=now,
        online=True,
    )
    assert schema.status == 'active'
    assert schema.user_name == 'alice'
    assert schema.endpoint == '203.0.113.10:54321'
    assert schema.online is True


async def test_async_operation_round_trip(db):
    operation = AsyncOperation(
        kind='provision_node',
        target_type='node',
        target_id='node-1',
        status='pending',
        idempotency_key='provision-node-1',
    )
    db.add(operation)
    await db.commit()

    result = await db.scalar(
        select(AsyncOperation).where(AsyncOperation.idempotency_key == 'provision-node-1')
    )

    assert result is not None
    assert result.kind == 'provision_node'
    assert result.target_type == 'node'
    assert result.target_id == 'node-1'
    assert result.status == 'pending'
    assert result.attempts == 0
    assert result.error is None
    assert result.result is None
    assert result.created_at is not None
    assert result.updated_at is not None
    assert result.finished_at is None


async def test_node_cached_status_defaults(db):
    node = Node(name='test-node', url='http://node:8000', token='secret')  # noqa: S106
    db.add(node)
    await db.commit()

    result = await db.scalar(select(Node).where(Node.id == node.id))

    assert result is not None
    assert result.health_status == 'unknown'
    assert result.last_seen_at is None
    assert result.provision_status == 'pending'
