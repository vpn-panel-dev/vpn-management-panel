from fastapi import APIRouter

from app.routers.internal_worker_parts.common import DB
from app.services.traffic_retention import cleanup_raw_traffic_samples

router = APIRouter()


@router.post('/traffic/cleanup-raw-samples')
async def cleanup_raw_samples(db: DB):
    result = await cleanup_raw_traffic_samples(db)
    return {
        'status': 'ok',
        'retention_days': result.retention_days,
        'deleted': result.deleted,
        'disabled': result.disabled,
        'cutoff': result.cutoff.isoformat() if result.cutoff else None,
    }
