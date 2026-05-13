from fastapi import APIRouter, HTTPException

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


# ── Nodes ─────────────────────────────────────────────────────────────────────
