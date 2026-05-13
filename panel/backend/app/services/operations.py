import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AsyncOperation

log = logging.getLogger(__name__)


def new_operation(kind: str, target_type: str | None, target_id: str | None) -> AsyncOperation:
    return AsyncOperation(
        id=str(uuid.uuid4()),
        kind=kind,
        target_type=target_type,
        target_id=target_id,
        status='queued',
        idempotency_key=str(uuid.uuid4()),
    )


def operation_response(operation: AsyncOperation) -> dict[str, str]:
    return {
        'operation_id': operation.id,
        'status_url': f'/api/operations/{operation.id}',
    }


async def enqueue_operation(
    db: AsyncSession,
    operation: AsyncOperation,
    enqueue: Callable[..., Awaitable[dict[str, Any]]],
    *args: Any,
) -> None:
    db.add(operation)
    await db.commit()
    try:
        await enqueue(
            *args,
            operation_id=operation.id,
            idempotency_key=operation.idempotency_key,
        )
    except Exception as exc:
        operation.status = 'enqueue_failed'
        operation.error = str(exc)[:500]
        await db.commit()
        log.warning('Failed to enqueue %s operation %s: %s', operation.kind, operation.id, exc)
