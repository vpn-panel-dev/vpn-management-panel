from __future__ import annotations

from datetime import datetime
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, Field, model_validator

CommandName = Literal[
    'sync_all',
    'sync_node',
    'provision_node',
    'health_check_all',
    'health_check_node',
    'cleanup_raw_traffic_samples',
    'remnawave_full_reconcile',
    'remnawave_sync_user',
    'remnawave_disable_user',
    'telegram_proxy_apply_node',
    'telegram_proxy_check_node',
    'telegram_proxy_disable_node',
]
TargetType = Literal['all', 'node', 'traffic', 'remnawave', 'remnawave_user', 'telegram_proxy_node']

TELEGRAM_PROXY_COMMANDS: Final = frozenset(
    {
        'telegram_proxy_apply_node',
        'telegram_proxy_check_node',
        'telegram_proxy_disable_node',
    }
)


class WorkerCommand(BaseModel):
    command: CommandName
    idempotency_key: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    track_operation: bool = True
    target_type: TargetType
    target_id: str | None = None
    created_at: datetime

    @property
    def name(self) -> CommandName:
        return self.command

    @property
    def node_id(self) -> str | None:
        return self.target_id

    @model_validator(mode='after')
    def validate_target_type(self) -> Self:
        if self.command in TELEGRAM_PROXY_COMMANDS and self.target_type != 'telegram_proxy_node':
            msg = 'Telegram proxy commands require target_type=telegram_proxy_node'
            raise ValueError(msg)
        return self


class CommandResult(BaseModel):
    command: CommandName
    node_id: str | None = None
    ok: bool
    detail: str | None = None
    result: dict[str, Any] | None = None
