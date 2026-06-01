from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.commands import CommandResult, WorkerCommand


def test_worker_command_accepts_remnawave_commands():
    now = datetime.now(UTC)
    cmd = WorkerCommand(
        command='remnawave_full_reconcile',
        idempotency_key=str(uuid.uuid4()),
        operation_id=str(uuid.uuid4()),
        target_type='remnawave',
        target_id=None,
        created_at=now,
    )

    assert cmd.name == 'remnawave_full_reconcile'


def test_worker_command_accepts_cleanup_raw_traffic_samples():
    cmd = WorkerCommand.model_validate(
        {
            'command': 'cleanup_raw_traffic_samples',
            'idempotency_key': 'idem-traffic-cleanup',
            'operation_id': 'op-traffic-cleanup',
            'target_type': 'traffic',
            'target_id': None,
            'created_at': '2026-01-01T00:00:00Z',
        }
    )

    assert cmd.name == 'cleanup_raw_traffic_samples'
    assert cmd.target_type == 'traffic'
    assert cmd.node_id is None


def test_worker_command_accepts_remnawave_sync_user():
    now = datetime.now(UTC)
    cmd = WorkerCommand(
        command='remnawave_sync_user',
        idempotency_key=str(uuid.uuid4()),
        operation_id=str(uuid.uuid4()),
        target_type='remnawave_user',
        target_id='user-123',
        created_at=now,
    )

    assert cmd.name == 'remnawave_sync_user'
    assert cmd.target_type == 'remnawave_user'
    assert cmd.node_id == 'user-123'


def test_worker_command_accepts_remnawave_disable_user():
    now = datetime.now(UTC)
    cmd = WorkerCommand(
        command='remnawave_disable_user',
        idempotency_key=str(uuid.uuid4()),
        operation_id=str(uuid.uuid4()),
        target_type='remnawave_user',
        target_id='user-123',
        created_at=now,
    )

    assert cmd.name == 'remnawave_disable_user'
    assert cmd.target_type == 'remnawave_user'
    assert cmd.node_id == 'user-123'


def test_command_result_accepts_remnawave_command():
    result = CommandResult(
        command='remnawave_full_reconcile',
        ok=True,
        detail='reconciled',
        result={'count': 5},
    )

    assert result.command == 'remnawave_full_reconcile'
    assert result.ok is True
