from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.models import AsyncOperation
from app.routers.api_parts.common import DB
from app.services.operations import enqueue_operation, new_operation, operation_response

router = APIRouter()

RETRYABLE_OPERATION_KINDS = {
    'sync_all',
    'sync_node',
    'provision_node',
    'cleanup_raw_traffic_samples',
    'remnawave_full_reconcile',
    'remnawave_sync_user',
    'remnawave_disable_user',
}


def _resolution_state(operation: AsyncOperation) -> str | None:
    if operation.status == 'failed_by_timeout':
        return 'needs_manual_action'
    if operation.status in {'failed', 'enqueue_failed'}:
        return 'recoverable'
    return None


def _can_retry(operation: AsyncOperation) -> bool:
    return operation.kind in RETRYABLE_OPERATION_KINDS and operation.status in {
        'failed',
        'failed_by_timeout',
        'enqueue_failed',
    }


def _serialize_operation(operation: AsyncOperation) -> dict[str, Any]:
    return {
        'id': operation.id,
        'kind': operation.kind,
        'target_type': operation.target_type,
        'target_id': operation.target_id,
        'status': operation.status,
        'error': operation.error,
        'result': operation.result,
        'attempts': operation.attempts,
        'created_at': operation.created_at,
        'updated_at': operation.updated_at,
        'finished_at': operation.finished_at,
        'resolution_state': _resolution_state(operation),
        'can_retry': _can_retry(operation),
    }


async def _enqueue_retry(db: DB, operation: AsyncOperation) -> dict[str, Any]:
    from app.routers import api as api_router

    retried_operation = new_operation(operation.kind, operation.target_type, operation.target_id)
    if operation.kind == 'sync_all':
        await enqueue_operation(db, retried_operation, api_router.enqueue_sync_all)
    elif operation.kind == 'sync_node':
        await enqueue_operation(
            db,
            retried_operation,
            api_router.enqueue_sync_node,
            operation.target_id,
        )
    elif operation.kind == 'provision_node':
        await enqueue_operation(
            db,
            retried_operation,
            api_router.enqueue_provision_node,
            operation.target_id,
        )
    elif operation.kind == 'cleanup_raw_traffic_samples':
        await enqueue_operation(
            db,
            retried_operation,
            api_router.enqueue_cleanup_raw_traffic_samples,
        )
    elif operation.kind == 'remnawave_full_reconcile':
        await enqueue_operation(
            db,
            retried_operation,
            api_router.enqueue_remnawave_full_reconcile,
        )
    elif operation.kind == 'remnawave_sync_user':
        await enqueue_operation(
            db,
            retried_operation,
            api_router.enqueue_remnawave_sync_user,
            operation.target_id,
        )
    elif operation.kind == 'remnawave_disable_user':
        await enqueue_operation(
            db,
            retried_operation,
            api_router.enqueue_remnawave_disable_user,
            operation.target_id,
        )
    else:
        raise HTTPException(status_code=409, detail='Operation kind cannot be retried')
    return operation_response(retried_operation)


@router.post('/sync', status_code=202)
async def api_trigger_sync(db: DB):
    """Manually trigger a sync cycle (useful for development/testing)."""
    operation = new_operation('sync_all', 'all', None)
    from app.routers import api as api_router

    await enqueue_operation(db, operation, api_router.enqueue_sync_all)
    cleanup_operation = new_operation('cleanup_raw_traffic_samples', 'traffic', None)
    await enqueue_operation(db, cleanup_operation, api_router.enqueue_cleanup_raw_traffic_samples)
    return operation_response(operation)


@router.get('/operations/{operation_id}')
async def api_get_operation(operation_id: str, db: DB):
    operation = await db.get(AsyncOperation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail='Operation not found')
    return _serialize_operation(operation)


@router.get('/operations')
async def api_list_operations(
    db: DB,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    query = select(AsyncOperation).order_by(AsyncOperation.updated_at.desc()).limit(limit)
    if status:
        query = query.where(AsyncOperation.status == status)
    operations = (await db.execute(query)).scalars().all()
    return [_serialize_operation(operation) for operation in operations]


@router.post('/operations/{operation_id}/retry', status_code=202)
async def api_retry_operation(operation_id: str, db: DB):
    operation = await db.get(AsyncOperation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail='Operation not found')
    if not _can_retry(operation):
        raise HTTPException(status_code=409, detail='Operation cannot be retried')
    return await _enqueue_retry(db, operation)


# ── Nodes ─────────────────────────────────────────────────────────────────────
