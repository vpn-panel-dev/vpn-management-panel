from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CommandName = Literal[
    'sync_all',
    'sync_node',
    'provision_node',
    'cleanup_raw_traffic_samples',
    'remnawave_full_reconcile',
    'remnawave_sync_user',
    'remnawave_disable_user',
]
TargetType = Literal['all', 'node', 'traffic', 'remnawave', 'remnawave_user']


class WorkerCommand(BaseModel):
    command: CommandName
    idempotency_key: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    target_type: TargetType
    target_id: str | None = None
    created_at: datetime

    @property
    def name(self) -> CommandName:
        return self.command

    @property
    def node_id(self) -> str | None:
        return self.target_id


class CommandResult(BaseModel):
    command: CommandName
    node_id: str | None = None
    ok: bool
    detail: str | None = None
    result: dict[str, Any] | None = None
