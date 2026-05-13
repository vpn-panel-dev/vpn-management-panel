import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.models import RemnawaveSettings, RemnawaveWebhookEvent
from app.remnawave_crypto import decrypt
from app.routers.api_parts.common import DB

_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300

webhook_router = APIRouter(prefix='/api')


def _webhook_event_key(payload: dict[str, Any]) -> str:
    event_type = payload.get('event') or payload.get('type')
    timestamp = payload.get('timestamp') or payload.get('created_at') or ''
    user_uuid = payload.get('data', {}).get('uuid') if isinstance(payload.get('data'), dict) else ''
    return f'{event_type}:{timestamp}:{user_uuid or ""}'


@webhook_router.post('/remnawave/webhook')
async def remnawave_webhook(request: Request, db: DB):
    body = await request.body()
    settings = await RemnawaveSettings.get_settings(db)
    if not settings.enabled or not settings.webhook_secret:
        raise HTTPException(status_code=401, detail='Remnawave webhook is not configured')

    signature = request.headers.get('X-Remnawave-Signature')
    timestamp = request.headers.get('X-Remnawave-Timestamp')
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail='Invalid webhook signature')
    try:
        event_ts = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid webhook timestamp') from exc
    if abs(int(datetime.now(UTC).timestamp()) - event_ts) > _WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
        raise HTTPException(status_code=400, detail='Webhook timestamp outside tolerance')

    secret = decrypt(settings.webhook_secret)
    if secret is None:
        raise HTTPException(status_code=401, detail='Remnawave webhook is not configured')
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail='Invalid webhook signature')

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail='Invalid webhook payload') from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail='Invalid webhook payload')
    event_type = payload.get('event') or payload.get('type')
    if not event_type:
        raise HTTPException(status_code=400, detail='Missing webhook event type')
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    user_uuid = data.get('uuid')
    event_key = _webhook_event_key(payload)

    existing = (
        await db.execute(
            select(RemnawaveWebhookEvent).where(RemnawaveWebhookEvent.event_key == event_key)
        )
    ).scalar_one_or_none()
    if existing:
        return {'status': 'already_processed'}

    db.add(
        RemnawaveWebhookEvent(
            event_key=event_key,
            event_type=event_type,
            remnawave_user_uuid=user_uuid,
        )
    )
    await db.commit()
    if user_uuid:
        from app.routers import api as api_router

        await api_router.enqueue_remnawave_sync_user(user_uuid)
    else:
        from app.routers import api as api_router

        await api_router.enqueue_remnawave_full_reconcile()
    return {'status': 'queued'}
