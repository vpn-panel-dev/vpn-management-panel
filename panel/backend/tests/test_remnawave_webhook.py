import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import RemnawaveSettings, RemnawaveWebhookEvent
from app.remnawave_crypto import encrypt


@pytest.fixture(autouse=True)
def _mock_remnawave_jobs():
    with (
        patch('app.routers.api.enqueue_remnawave_sync_user', new=AsyncMock()) as sync_user,
        patch(
            'app.routers.api.enqueue_remnawave_full_reconcile', new=AsyncMock()
        ) as full_reconcile,
    ):
        yield sync_user, full_reconcile


async def _configure(db, secret='webhook-secret'):  # noqa: S107
    db.add(RemnawaveSettings(enabled=True, webhook_secret=encrypt(secret)))
    await db.commit()
    return secret


def _signed(body: bytes, secret: str, timestamp: int | None = None) -> dict[str, str]:
    ts = timestamp or int(datetime.now(UTC).timestamp())
    return {
        'X-Remnawave-Timestamp': str(ts),
        'X-Remnawave-Signature': hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
    }


async def test_webhook_valid_user_event_deduplicates_and_enqueues_sync_user(
    client: AsyncClient, db, _mock_remnawave_jobs
):
    secret = await _configure(db)
    payload = {'event': 'user.updated', 'timestamp': 'event-1', 'data': {'uuid': 'rw-uuid-1'}}
    body = json.dumps(payload).encode()

    first = await client.post('/api/remnawave/webhook', content=body, headers=_signed(body, secret))
    replay = await client.post(
        '/api/remnawave/webhook', content=body, headers=_signed(body, secret)
    )

    sync_user, full_reconcile = _mock_remnawave_jobs
    assert first.status_code == HTTPStatus.OK
    assert first.json() == {'status': 'queued'}
    assert replay.status_code == HTTPStatus.OK
    assert replay.json() == {'status': 'already_processed'}
    sync_user.assert_awaited_once_with('rw-uuid-1')
    full_reconcile.assert_not_awaited()
    event = (await db.execute(select(RemnawaveWebhookEvent))).scalar_one()
    assert event.event_key == 'user.updated:event-1:rw-uuid-1'


async def test_webhook_without_uuid_enqueues_full_reconcile(
    client: AsyncClient, db, _mock_remnawave_jobs
):
    secret = await _configure(db)
    payload = {'event': 'system.updated', 'timestamp': 'event-2', 'data': {}}
    body = json.dumps(payload).encode()

    resp = await client.post('/api/remnawave/webhook', content=body, headers=_signed(body, secret))

    sync_user, full_reconcile = _mock_remnawave_jobs
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'status': 'queued'}
    sync_user.assert_not_awaited()
    full_reconcile.assert_awaited_once_with()


async def test_webhook_rejects_invalid_signature(client: AsyncClient, db):
    secret = await _configure(db)
    body = json.dumps({'event': 'user.updated', 'timestamp': 'event-3'}).encode()
    headers = _signed(body, secret)
    headers['X-Remnawave-Signature'] = 'bad-signature'

    resp = await client.post('/api/remnawave/webhook', content=body, headers=headers)

    assert resp.status_code == HTTPStatus.UNAUTHORIZED
    assert (await db.execute(select(RemnawaveWebhookEvent))).scalar_one_or_none() is None


async def test_webhook_rejects_old_timestamp(client: AsyncClient, db):
    secret = await _configure(db)
    body = json.dumps({'event': 'user.updated', 'timestamp': 'event-4'}).encode()
    old = int((datetime.now(UTC) - timedelta(seconds=301)).timestamp())

    resp = await client.post(
        '/api/remnawave/webhook', content=body, headers=_signed(body, secret, old)
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert (await db.execute(select(RemnawaveWebhookEvent))).scalar_one_or_none() is None
