from fastapi import APIRouter, Depends

from app.job_commands import (
    enqueue_remnawave_disable_user as enqueue_remnawave_disable_user,
    enqueue_sync_node as enqueue_sync_node,
)
from app.routers.internal_worker_parts import nodes, operations, remnawave, traffic
from app.routers.internal_worker_parts.auth import require_worker_token

router = APIRouter(prefix='/internal/worker', dependencies=[Depends(require_worker_token)])
router.include_router(remnawave.router)
router.include_router(operations.router)
router.include_router(nodes.router)
router.include_router(traffic.router)
