import json
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AsyncOperation
from app.routers.internal_worker_parts.common import DB
from app.schemas.worker import OperationResult
from app.services.remnawave_sync import now

router = APIRouter()


def _result_json(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(data, sort_keys=True, default=str)


async def _operation(db: AsyncSession, operation_id: str) -> AsyncOperation:
    operation = await db.get(AsyncOperation, operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail='Operation not found')
    return operation


def _ensure_status(operation: AsyncOperation, allowed: set[str]) -> None:
    if operation.status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f'Operation status {operation.status!r} cannot transition here',
        )


@router.post('/operations/{operation_id}/start')
async def start_operation(operation_id: str, db: DB):
    operation = await _operation(db, operation_id)
    _ensure_status(operation, {'queued', 'pending'})
    operation.status = 'running'
    operation.attempts += 1
    operation.error = None
    operation.updated_at = now()
    await db.commit()
    return {'status': operation.status, 'attempts': operation.attempts}


@router.post('/operations/{operation_id}/succeed')
async def succeed_operation(operation_id: str, data: OperationResult, db: DB):
    operation = await _operation(db, operation_id)
    _ensure_status(operation, {'running'})
    operation.status = 'succeeded'
    operation.error = None
    operation.result = _result_json(data.result)
    finished_at = now()
    operation.finished_at = finished_at
    operation.updated_at = finished_at
    await db.commit()
    return {'status': operation.status}


@router.post('/operations/{operation_id}/fail')
async def fail_operation(operation_id: str, data: OperationResult, db: DB):
    operation = await _operation(db, operation_id)
    _ensure_status(operation, {'running'})
    operation.status = 'failed'
    operation.error = data.error or 'Worker reported failure'
    operation.result = _result_json(data.result)
    finished_at = now()
    operation.finished_at = finished_at
    operation.updated_at = finished_at
    await db.commit()
    return {'status': operation.status}


@router.get('/operations/stale')
async def stale_operations(
    db: DB,
    status_filter: Annotated[str, Query(alias='status')],
    older_than_seconds: Annotated[int, Query(ge=0)],
):
    cutoff = now() - timedelta(seconds=older_than_seconds)
    operations = (
        (
            await db.execute(
                select(AsyncOperation)
                .where(
                    AsyncOperation.status == status_filter,
                    AsyncOperation.updated_at <= cutoff,
                )
                .order_by(AsyncOperation.updated_at)
            )
        )
        .scalars()
        .all()
    )
    return {
        'operations': [
            {
                'id': operation.id,
                'kind': operation.kind,
                'target_type': operation.target_type,
                'target_id': operation.target_id,
                'status': operation.status,
                'attempts': operation.attempts,
                'updated_at': operation.updated_at.isoformat(),
            }
            for operation in operations
        ]
    }
