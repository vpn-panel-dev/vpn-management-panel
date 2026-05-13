import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import allocate_ip, generate_keypair, generate_psk
from app.models import Node, Peer, User


class RemnawaveUserProvisionData(Protocol):
    username: str
    short_uuid: str | None


async def allocate_vpn_ip(db: AsyncSession) -> str:
    used_ips = {
        ip
        for ip in (await db.execute(select(User.vpn_ip).where(User.vpn_ip.isnot(None)))).scalars()
        if ip
    }
    return allocate_ip(used_ips)


async def list_nodes(db: AsyncSession) -> list[Node]:
    return list((await db.execute(select(Node))).scalars().all())


async def create_pending_peers_for_user(db: AsyncSession, user: User) -> set[str]:
    node_ids: set[str] = set()
    for node in await list_nodes(db):
        db.add(Peer(node_id=node.id, user_id=user.id, status='pending', psk_key=generate_psk()))
        node_ids.add(node.id)
    return node_ids


async def create_pending_peers_for_node(db: AsyncSession, node: Node) -> set[str]:
    users = (
        (
            await db.execute(
                select(User).where(User.is_blocked == False, User.public_key.isnot(None))  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    user_ids: set[str] = set()
    for user in users:
        db.add(Peer(node_id=node.id, user_id=user.id, status='pending', psk_key=generate_psk()))
        user_ids.add(user.id)
    return user_ids


async def create_local_user(db: AsyncSession, name: str, *, is_blocked: bool = False) -> User:
    private_key, public_key = generate_keypair()
    user = User(
        name=name,
        public_key=public_key,
        private_key=private_key,
        vpn_ip=await allocate_vpn_ip(db),
        is_blocked=is_blocked,
    )
    db.add(user)
    await db.flush()
    await create_pending_peers_for_user(db, user)
    return user


async def resolve_remnawave_username(db: AsyncSession, desired: str, short_uuid: str | None) -> str:
    existing = await db.execute(select(User).where(User.name == desired))
    if existing.scalar_one_or_none() is None:
        return desired
    suffix = short_uuid or str(uuid.uuid4())[:8]
    return f'{desired}__rw_{suffix}'


async def create_remnawave_local_user(
    db: AsyncSession,
    data: RemnawaveUserProvisionData,
    *,
    is_blocked: bool,
) -> tuple[User, set[str]]:
    private_key, public_key = generate_keypair()
    user = User(
        name=await resolve_remnawave_username(db, data.username, data.short_uuid),
        public_key=public_key,
        private_key=private_key,
        vpn_ip=await allocate_vpn_ip(db),
        is_blocked=is_blocked,
    )
    db.add(user)
    await db.flush()
    node_ids = await create_pending_peers_for_user(db, user)
    return user, node_ids
