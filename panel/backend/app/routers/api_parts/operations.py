from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.models import AsyncOperation
from app.routers.api_parts.common import DB
from app.services.operations import enqueue_operation, new_operation, operation_response

router = APIRouter()


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
    }


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
    return [
        {
            'id': operation.id,
            'kind': operation.kind,
            'target_type': operation.target_type,
            'target_id': operation.target_id,
            'status': operation.status,
            'error': operation.error,
            'attempts': operation.attempts,
            'created_at': operation.created_at,
            'updated_at': operation.updated_at,
            'finished_at': operation.finished_at,
        }
        for operation in operations
    ]


# ── Nodes ─────────────────────────────────────────────────────────────────────
