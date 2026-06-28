from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.commands import CommandResult, WorkerCommand


def test_worker_command_accepts_remnawave_commands():
    now = datetime.now(UTC)
    cmd = WorkerCommand(
        command='remnawave_full_reconcile',
        idempotency_key=str(uuid.uuid4()),
        operation_id=str(uuid.uuid4()),
        track_operation=True,
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
            'track_operation': False,
            'target_type': 'traffic',
            'target_id': None,
            'created_at': '2026-01-01T00:00:00Z',
        }
    )

    assert cmd.name == 'cleanup_raw_traffic_samples'
    assert cmd.target_type == 'traffic'
    assert cmd.node_id is None
    assert cmd.track_operation is False


def test_worker_command_accepts_remnawave_sync_user():
    now = datetime.now(UTC)
    cmd = WorkerCommand(
        command='remnawave_sync_user',
        idempotency_key=str(uuid.uuid4()),
        operation_id=str(uuid.uuid4()),
        track_operation=True,
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
        track_operation=True,
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


@pytest.mark.parametrize(
    'command',
    [
        'telegram_proxy_apply_node',
        'telegram_proxy_check_node',
        'telegram_proxy_disable_node',
    ],
)
def test_worker_command_accepts_telegram_proxy_node_commands(command: str) -> None:
    cmd = WorkerCommand.model_validate(
        {
            'command': command,
            'idempotency_key': f'idem-{command}',
            'operation_id': f'op-{command}',
            'track_operation': True,
            'target_type': 'telegram_proxy_node',
            'target_id': 'node-1',
            'created_at': '2026-01-01T00:00:00Z',
        }
    )

    assert cmd.name == command
    assert cmd.target_type == 'telegram_proxy_node'
    assert cmd.node_id == 'node-1'


def test_worker_command_rejects_telegram_proxy_wrong_target_type() -> None:
    with pytest.raises(ValidationError):
        WorkerCommand.model_validate(
            {
                'command': 'telegram_proxy_apply_node',
                'idempotency_key': 'idem-telegram-proxy-apply',
                'operation_id': 'op-telegram-proxy-apply',
                'track_operation': True,
                'target_type': 'node',
                'target_id': 'node-1',
                'created_at': '2026-01-01T00:00:00Z',
            }
        )


def test_worker_command_rejects_arbitrary_command_string() -> None:
    with pytest.raises(ValidationError):
        WorkerCommand.model_validate(
            {
                'command': 'telegram_proxy_restart_everything',
                'idempotency_key': 'idem-arbitrary-command',
                'operation_id': 'op-arbitrary-command',
                'track_operation': True,
                'target_type': 'telegram_proxy_node',
                'target_id': 'node-1',
                'created_at': '2026-01-01T00:00:00Z',
            }
        )
