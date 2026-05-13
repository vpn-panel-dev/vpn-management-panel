from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from .queue import PROVISION_ROUTING_KEY, SYNC_ROUTING_KEY, publish_command


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _payload(
    command: str,
    *,
    target_type: str,
    target_id: str | None,
    **overrides: Any,
) -> dict[str, Any]:
    return {
        'command': command,
        'idempotency_key': overrides.get('idempotency_key') or str(uuid.uuid4()),
        'operation_id': overrides.get('operation_id') or str(uuid.uuid4()),
        'target_type': target_type,
        'target_id': target_id,
        'created_at': overrides.get('created_at') or _now(),
    }


def sync_all(**overrides: Any) -> dict[str, Any]:
    return _payload('sync_all', target_type='all', target_id=None, **overrides)


def sync_node(node_id: str, **overrides: Any) -> dict[str, Any]:
    return _payload('sync_node', target_type='node', target_id=node_id, **overrides)


def provision_node(node_id: str, **overrides: Any) -> dict[str, Any]:
    return _payload('provision_node', target_type='node', target_id=node_id, **overrides)


async def enqueue_sync_all(*, url: str | None = None, **overrides: Any) -> dict[str, Any]:
    payload = sync_all(**overrides)
    await publish_command(payload, SYNC_ROUTING_KEY, url=url)
    return payload


async def enqueue_sync_node(
    node_id: str,
    *,
    url: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload = sync_node(node_id, **overrides)
    await publish_command(payload, SYNC_ROUTING_KEY, url=url)
    return payload


async def enqueue_provision_node(
    node_id: str,
    *,
    url: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload = provision_node(node_id, **overrides)
    await publish_command(payload, PROVISION_ROUTING_KEY, url=url)
    return payload


def remnawave_full_reconcile(**overrides: Any) -> dict[str, Any]:
    return _payload(
        'remnawave_full_reconcile',
        target_type='remnawave',
        target_id=None,
        **overrides,
    )


def remnawave_sync_user(user_uuid: str, **overrides: Any) -> dict[str, Any]:
    return _payload(
        'remnawave_sync_user',
        target_type='remnawave_user',
        target_id=user_uuid,
        **overrides,
    )


async def enqueue_remnawave_full_reconcile(
    *,
    url: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload = remnawave_full_reconcile(**overrides)
    await publish_command(payload, SYNC_ROUTING_KEY, url=url)
    return payload


async def enqueue_remnawave_sync_user(
    user_uuid: str,
    *,
    url: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload = remnawave_sync_user(user_uuid, **overrides)
    await publish_command(payload, SYNC_ROUTING_KEY, url=url)
    return payload
