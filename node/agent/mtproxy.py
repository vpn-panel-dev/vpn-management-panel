from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_CONFIG_PATH: Final = Path('/etc/amnezia/mtproxy/config.json')
SUPERVISOR_TIMEOUT_SECONDS: Final = 5.0
REDACTED: Final = '<redacted>'
SUPERVISOR_STATE_PARTS: Final = 2

type MTProxyState = Literal['disabled', 'running', 'stopped', 'failed']
type SupervisorAction = Literal['start', 'stop', 'restart', 'status']
type SupervisorRunner = Callable[[list[str], float], subprocess.CompletedProcess[str]]


class MTProxyConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    port: int = Field(ge=1, le=65535)
    public_host: str = Field(min_length=1)
    secret: str = Field(min_length=1)


class MTProxyStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: MTProxyState
    port: int | None
    public_host: str | None
    secret_set: bool


class SupervisorProcessState(StrEnum):
    RUNNING = 'RUNNING'
    STARTING = 'STARTING'
    STOPPED = 'STOPPED'
    EXITED = 'EXITED'
    FATAL = 'FATAL'
    BACKOFF = 'BACKOFF'
    UNKNOWN = 'UNKNOWN'


@dataclass(frozen=True, slots=True)
class SupervisorCommandError(Exception):
    action: SupervisorAction
    returncode: int

    def __str__(self) -> str:
        return f'supervisorctl {self.action} mtproxy failed with exit code {self.returncode}'


@dataclass(frozen=True, slots=True)
class SupervisorTimeoutError(Exception):
    action: SupervisorAction

    def __str__(self) -> str:
        return f'supervisorctl {self.action} mtproxy timed out'


def apply_mtproxy_config(
    config: MTProxyConfig,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_json = config.model_dump_json(indent=2) + '\n'
    fd, temp_name = tempfile.mkstemp(prefix='.config.', suffix='.tmp', dir=config_path.parent)
    temp_path = Path(temp_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as temp_file:
            temp_file.write(config_json)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_path.replace(config_path)
        config_path.chmod(0o600)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def remove_mtproxy_config(*, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    config_path.unlink(missing_ok=True)


def _run_supervisor(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def supervisor_mtproxy(
    action: SupervisorAction,
    *,
    runner: SupervisorRunner = _run_supervisor,
    timeout: float = SUPERVISOR_TIMEOUT_SECONDS,
) -> str:
    try:
        result = runner(['supervisorctl', action, 'mtproxy'], timeout)
    except subprocess.TimeoutExpired as exc:
        raise SupervisorTimeoutError(action=action) from exc
    if result.returncode != 0:
        raise SupervisorCommandError(action=action, returncode=result.returncode)
    return result.stdout.strip()


def read_mtproxy_status(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    runner: SupervisorRunner = _run_supervisor,
) -> MTProxyStatus:
    try:
        supervisor_output = supervisor_mtproxy('status', runner=runner)
    except SupervisorCommandError:
        config = _load_config(config_path)
        if config is None:
            return MTProxyStatus(state='disabled', port=None, public_host=None, secret_set=False)
        return MTProxyStatus(
            state='disabled',
            port=config.port,
            public_host=config.public_host,
            secret_set=bool(config.secret),
        )
    return parse_mtproxy_status(supervisor_output, config_path=config_path)


def parse_mtproxy_status(
    supervisor_output: str,
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> MTProxyStatus:
    config = _load_config(config_path)
    if config is None:
        return MTProxyStatus(state='disabled', port=None, public_host=None, secret_set=False)
    return MTProxyStatus(
        state=_parse_supervisor_state(supervisor_output),
        port=config.port,
        public_host=config.public_host,
        secret_set=bool(config.secret),
    )


def _load_config(config_path: Path) -> MTProxyConfig | None:
    if not config_path.exists():
        return None
    return MTProxyConfig.model_validate_json(config_path.read_text())


def _parse_supervisor_state(supervisor_output: str) -> MTProxyState:
    state = _extract_supervisor_state(supervisor_output)
    match state:
        case SupervisorProcessState.RUNNING | SupervisorProcessState.STARTING:
            return 'running'
        case SupervisorProcessState.STOPPED | SupervisorProcessState.EXITED:
            return 'stopped'
        case (
            SupervisorProcessState.FATAL
            | SupervisorProcessState.BACKOFF
            | SupervisorProcessState.UNKNOWN
        ):
            return 'failed'
        case _ as unreachable:
            assert_never(unreachable)


def _extract_supervisor_state(supervisor_output: str) -> SupervisorProcessState:
    parts = supervisor_output.split()
    if len(parts) < SUPERVISOR_STATE_PARTS:
        return SupervisorProcessState.UNKNOWN
    candidate = parts[1]
    try:
        return SupervisorProcessState(candidate)
    except ValueError:
        return SupervisorProcessState.UNKNOWN
