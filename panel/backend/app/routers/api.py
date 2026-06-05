from fastapi import APIRouter, Depends

from app.job_commands import (
    enqueue_cleanup_raw_traffic_samples as enqueue_cleanup_raw_traffic_samples,
    enqueue_health_check_all as enqueue_health_check_all,
    enqueue_health_check_node as enqueue_health_check_node,
    enqueue_provision_node as enqueue_provision_node,
    enqueue_remnawave_full_reconcile as enqueue_remnawave_full_reconcile,
    enqueue_remnawave_sync_user as enqueue_remnawave_sync_user,
    enqueue_sync_all as enqueue_sync_all,
    enqueue_sync_node as enqueue_sync_node,
)
from app.routers.api_parts import configs, nodes, operations, remnawave, users
from app.routers.auth import require_auth

router = APIRouter(prefix='/api', dependencies=[Depends(require_auth)])
router.include_router(operations.router)
router.include_router(nodes.router)
router.include_router(users.router)
router.include_router(configs.router)

webhook_router = remnawave.webhook_router
