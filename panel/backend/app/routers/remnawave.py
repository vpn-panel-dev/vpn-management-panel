from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.job_commands import enqueue_remnawave_full_reconcile
from app.models import (
    RemnawaveSettings,
    RemnawaveSettingsIn,
    RemnawaveSettingsSchema,
)
from app.remnawave_crypto import decrypt, encrypt
from app.routers.auth import require_auth
from app.services.operations import enqueue_operation, new_operation, operation_response

router = APIRouter(prefix='/api/remnawave', dependencies=[Depends(require_auth)])
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get('/settings')
async def get_remnawave_settings(db: DB):
    """Return current Remnawave settings (secrets exposed only as booleans)."""
    settings = await RemnawaveSettings.get_settings(db)
    return RemnawaveSettingsSchema.from_orm(settings)


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


@router.get('/status')
async def get_remnawave_status(db: DB):
    """Return the last test and sync status for Remnawave."""
    settings = await RemnawaveSettings.get_settings(db)
    return {
        'enabled': settings.enabled,
        'base_url': settings.base_url,
        'last_tested_at': settings.last_tested_at.isoformat() if settings.last_tested_at else None,
        'last_test_status': settings.last_test_status,
        'last_test_error': settings.last_test_error,
    }
