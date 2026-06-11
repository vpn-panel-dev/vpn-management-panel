import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import RemnawaveSettings, RemnawaveUser, User
from app.remnawave_crypto import decrypt
from app.routers.internal_worker_parts.common import DB
from app.schemas.worker import RemnawaveReconcileCompleteIn, RemnawaveUserIn
from app.services.remnawave_sync import (
    apply_remnawave_lifecycle,
    apply_remnawave_profile,
    aware,
    enforce_remnawave_combined_limit,
    enqueue_remnawave_disable_users,
    enqueue_sync_nodes,
    now,
    purge_confirmed_remnawave_deletes,
    reconcile_missing_remnawave_users,
    remnawave_blocked,
)
from app.services.users import create_remnawave_local_user

router = APIRouter()
log = logging.getLogger(__name__)


def _worker_error_detail(context: str, exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return f'{context}: {message}'


@router.get('/remnawave/config')
async def get_remnawave_config(db: DB):
    settings = await RemnawaveSettings.get_settings(db)
    return {
        'base_url': settings.base_url,
        'api_token': decrypt(settings.api_token) if settings.api_token else None,
        'enabled': settings.enabled,
    }


@router.get('/remnawave/polling-state')
async def get_remnawave_polling_state(db: DB):
    settings = await RemnawaveSettings.get_settings(db)
    if not settings.enabled or not settings.polling_enabled:
        return {'enabled': False, 'due': False}
    last_synced_at = aware(settings.last_synced_at)
    due = (
        last_synced_at is None
        or (now() - last_synced_at).total_seconds() >= settings.polling_interval_seconds
    )
    return {'enabled': True, 'due': due}


@router.post('/remnawave/users/upsert')
async def upsert_remnawave_users(data: list[RemnawaveUserIn], db: DB):
    try:
        return await _upsert_remnawave_users(data, db)
    except Exception as exc:
        await db.rollback()
        log.exception('Remnawave users upsert failed')
        raise HTTPException(
            status_code=500,
            detail=_worker_error_detail('Remnawave users upsert failed', exc),
        ) from exc


async def _upsert_remnawave_users(data: list[RemnawaveUserIn], db: DB):
    affected_node_ids: set[str] = set()
    remote_disable_uuids: set[str] = set()
    upserted: list[str] = []
    for item in data:
        row = (
            await db.execute(
                select(RemnawaveUser)
                .where(RemnawaveUser.remnawave_uuid == item.uuid)
                .options(selectinload(RemnawaveUser.user).selectinload(User.peers))
            )
        ).scalar_one_or_none()

        if row is None:
            user, created_node_ids = await create_remnawave_local_user(
                db,
                item,
                is_blocked=remnawave_blocked(item),
            )
            row = RemnawaveUser(
                user_id=user.id,
                remnawave_uuid=item.uuid,
                username=item.username,
                status=item.status,
            )
            db.add(row)
            await db.flush()
            affected_node_ids.update(created_node_ids)
        else:
            affected_node_ids.update(apply_remnawave_lifecycle(row, item))

        apply_remnawave_profile(row, item)
        limited_node_ids, limited_user_uuids = await enforce_remnawave_combined_limit(db, row)
        affected_node_ids.update(limited_node_ids)
        remote_disable_uuids.update(limited_user_uuids)
        upserted.append(item.uuid)

    await db.commit()
    await enqueue_sync_nodes(db, affected_node_ids)
    await enqueue_remnawave_disable_users(db, remote_disable_uuids)
    return {
        'upserted': upserted,
        'affected_node_ids': sorted(affected_node_ids),
        'remote_disable_uuids': sorted(remote_disable_uuids),
    }


@router.post('/remnawave/users/{user_uuid}/deleted')
async def mark_remnawave_user_deleted(user_uuid: str, db: DB):
    row = (
        await db.execute(
            select(RemnawaveUser)
            .where(RemnawaveUser.remnawave_uuid == user_uuid)
            .options(selectinload(RemnawaveUser.user).selectinload(User.peers))
        )
    ).scalar_one_or_none()
    if row is None:
        return {'status': 'not_found', 'affected_node_ids': []}

    row.delete_requested_at = row.delete_requested_at or now()
    row.sync_status = 'missing'
    row.sync_reason = 'delete requested'
    row.user.is_blocked = True
    affected_node_ids: set[str] = set()
    for peer in row.user.peers:
        if peer.status != 'deleted':
            peer.status = 'pending_delete'
            affected_node_ids.add(peer.node_id)
    await db.commit()
    await enqueue_sync_nodes(db, affected_node_ids)
    return {'status': 'delete_requested', 'affected_node_ids': sorted(affected_node_ids)}


@router.post('/remnawave/reconcile-complete')
async def remnawave_reconcile_complete(data: RemnawaveReconcileCompleteIn, db: DB):
    settings = await RemnawaveSettings.get_settings(db)
    affected_node_ids = await reconcile_missing_remnawave_users(db, set(data.seen_uuids))
    settings.last_synced_at = now()
    purged = await purge_confirmed_remnawave_deletes(db)
    await db.commit()
    await enqueue_sync_nodes(db, affected_node_ids)
    return {
        'status': 'ok',
        'purged': purged,
        'affected_node_ids': sorted(affected_node_ids),
    }
