from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.job_commands import enqueue_remnawave_full_reconcile, enqueue_remnawave_sync_user
from app.models import (
    AsyncOperation,
    LocalAmneziawgTrafficSettings,
    LocalAmneziawgTrafficSettingsIn,
    LocalAmneziawgTrafficSettingsSchema,
    RemnawaveSettings,
    RemnawaveSettingsIn,
    RemnawaveSettingsSchema,
    RemnawaveUser,
)
from app.remnawave_crypto import decrypt, encrypt
from app.routers.auth import require_auth
from app.services.operations import enqueue_operation, new_operation, operation_response

router = APIRouter(prefix='/api/remnawave', dependencies=[Depends(require_auth)])
DB = Annotated[AsyncSession, Depends(get_db)]


async def _remnawave_status(db: AsyncSession) -> dict[str, object]:
    settings = await RemnawaveSettings.get_settings(db)

    imported_users_count = await db.scalar(select(func.count()).select_from(RemnawaveUser))
    pending_node_sync_count = await db.scalar(
        select(func.count()).select_from(RemnawaveUser).where(RemnawaveUser.sync_status != 'synced')
    )
    last_successful_reconcile_at = (
        settings.last_synced_at.isoformat() if settings.last_synced_at else None
    )

    failed_reconcile = (
        (
            await db.execute(
                select(AsyncOperation)
                .where(
                    AsyncOperation.kind == 'remnawave_full_reconcile',
                    AsyncOperation.status.in_({'failed', 'enqueue_failed'}),
                )
                .order_by(AsyncOperation.updated_at.desc())
            )
        )
        .scalars()
        .first()
    )

    return {
        'enabled': settings.enabled,
        'base_url': settings.base_url,
        'last_successful_reconcile_at': last_successful_reconcile_at,
        'last_failed_reconcile_at': (
            failed_reconcile.updated_at.isoformat() if failed_reconcile else None
        ),
        'last_error': failed_reconcile.error if failed_reconcile else None,
        'imported_users_count': imported_users_count or 0,
        'pending_node_sync_count': pending_node_sync_count or 0,
        'last_tested_at': (
            settings.last_tested_at.isoformat() if settings.last_tested_at else None
        ),
        'last_test_status': settings.last_test_status,
        'last_test_error': settings.last_test_error,
    }


@router.get('/settings')
async def get_remnawave_settings(db: DB):
    """Return current Remnawave settings (secrets exposed only as booleans)."""
    settings = await RemnawaveSettings.get_settings(db)
    return RemnawaveSettingsSchema.from_orm(settings)


@router.get('/local-traffic/settings', response_model=LocalAmneziawgTrafficSettingsSchema)
async def get_local_traffic_settings(db: DB):
    settings = await LocalAmneziawgTrafficSettings.get_settings(db)
    return settings


@router.put('/local-traffic/settings', response_model=LocalAmneziawgTrafficSettingsSchema)
async def update_local_traffic_settings(data: LocalAmneziawgTrafficSettingsIn, db: DB):
    settings = await LocalAmneziawgTrafficSettings.get_settings(db)
    settings.raw_sample_retention_days = data.raw_sample_retention_days
    await db.commit()
    await db.refresh(settings)
    return settings


@router.put('/settings')
async def update_remnawave_settings(data: RemnawaveSettingsIn, db: DB):
    """Update Remnawave settings. Blank token/secret keeps existing; explicit
    clear_* flags remove them."""
    settings = await RemnawaveSettings.get_settings(db)

    if data.base_url is not None:
        settings.base_url = data.base_url
    settings.enabled = data.enabled
    settings.polling_enabled = data.polling_enabled
    settings.polling_interval_seconds = data.polling_interval_seconds
    if data.subscription_url is not None:
        settings.subscription_url = data.subscription_url

    if data.clear_api_token:
        settings.api_token = None
    elif data.api_token is not None and data.api_token != '':
        settings.api_token = encrypt(data.api_token)

    if data.clear_webhook_secret:
        settings.webhook_secret = None
    elif data.webhook_secret is not None and data.webhook_secret != '':
        settings.webhook_secret = encrypt(data.webhook_secret)

    await db.commit()
    await db.refresh(settings)
    return RemnawaveSettingsSchema.from_orm(settings)


@router.post('/test')
async def test_remnawave_connection(db: DB):
    """Test connection to the Remnawave API and record the result."""
    settings = await RemnawaveSettings.get_settings(db)

    if not settings.base_url:
        raise HTTPException(status_code=400, detail='Remnawave base URL is not configured')

    token = decrypt(settings.api_token)
    if not token:
        raise HTTPException(status_code=400, detail='Remnawave API token is not configured')

    success = False
    error_message = None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f'{settings.base_url}/api/users?start=0&size=1',
                headers={'Authorization': f'Bearer {token}'},
            )
            response.raise_for_status()
            success = True
    except httpx.HTTPStatusError as exc:
        error_message = f'HTTP {exc.response.status_code}: {exc.response.text}'
    except httpx.RequestError as exc:
        error_message = f'Request failed: {exc}'
    except Exception as exc:
        error_message = str(exc)

    settings.last_tested_at = datetime.now(UTC)
    settings.last_test_status = 'success' if success else 'failed'
    settings.last_test_error = error_message
    await db.commit()
    await db.refresh(settings)

    return {'success': success, 'error': error_message}


@router.post('/sync', status_code=202)
async def trigger_remnawave_sync(db: DB):
    """Trigger a manual full reconcile with Remnawave."""
    operation = new_operation('remnawave_full_reconcile', 'remnawave', None)
    await enqueue_operation(db, operation, enqueue_remnawave_full_reconcile)
    return operation_response(operation)


@router.post('/users/{user_uuid}/sync', status_code=202)
async def trigger_remnawave_user_sync(user_uuid: UUID, db: DB):
    settings = await RemnawaveSettings.get_settings(db)
    if not settings.enabled:
        raise HTTPException(status_code=409, detail='Remnawave is disabled')

    operation = new_operation('remnawave_sync_user', 'remnawave_user', str(user_uuid))
    await enqueue_operation(db, operation, enqueue_remnawave_sync_user, str(user_uuid))
    return operation_response(operation)


@router.get('/status')
async def get_remnawave_status(db: DB):
    """Return the last test and sync status for Remnawave."""
    return await _remnawave_status(db)
