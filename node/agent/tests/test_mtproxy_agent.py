from __future__ import annotations

import json
import os
import stat
import subprocess
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import agent
import mtproxy
from mtproxy import (
    DEFAULT_CONFIG_PATH,
    MTProxyConfig,
    SupervisorCommandError,
    SupervisorTimeoutError,
    apply_mtproxy_config,
    parse_mtproxy_status,
    read_mtproxy_status,
    remove_mtproxy_config,
    supervisor_mtproxy,
)

RAW_SECRET = '0123456789abcdef0123456789abcdef'
AUTH_HEADERS = {'Authorization': 'Bearer test-token'}


@pytest.fixture()
def mtproxy_config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / 'mtproxy' / 'config.json'
    monkeypatch.setattr(agent, 'MTPROXY_CONFIG_PATH', config_path, raising=False)
    return config_path


def _payload() -> dict[str, object]:
    return {'port': 443, 'public_host': 'proxy.example.com', 'secret': RAW_SECRET}


def _run_mtproxy_wrapper(config_dir: Path, config_path: Path) -> subprocess.CompletedProcess[str]:
    wrapper_path = Path(__file__).parents[2] / 'mtproxy.sh'
    env = os.environ | {
        'MTPROXY_CONFIG_DIR': str(config_dir),
        'MTPROXY_CONFIG_FILE': str(config_path),
        'MTPROXY_DRY_RUN': '1',
        'MTPROXY_SKIP_FETCH': '1',
        'MTPROXY_NAT_INTERNAL_IP': '172.19.0.2',
        'MTPROXY_NAT_PUBLIC_IP': '95.85.230.107',
    }
    return subprocess.run(  # noqa: S603
        ['/bin/bash', str(wrapper_path)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        env=env,
    )


def _run_mtproxy_wrapper_with_path(
    config_dir: Path,
    config_path: Path,
    path: Path,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    base_path = os.environ.get('PATH', '')
    env = os.environ | {
        'PATH': f'{path}:{base_path}' if base_path else str(path),
        'MTPROXY_CONFIG_DIR': str(config_dir),
        'MTPROXY_CONFIG_FILE': str(config_path),
        'MTPROXY_DRY_RUN': '1',
        'MTPROXY_SKIP_FETCH': '1',
    }
    if extra_env:
        env |= extra_env
    wrapper_path = Path(__file__).parents[2] / 'mtproxy.sh'
    return subprocess.run(  # noqa: S603
        ['/bin/bash', str(wrapper_path)],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
        env=env,
    )


def test_mtproxy_default_config_path_uses_existing_node_config_mount() -> None:
    assert Path('/etc/amnezia/amneziawg/mtproxy/config.json') == DEFAULT_CONFIG_PATH


def test_mtproxy_config_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        MTProxyConfig(port=70000, public_host='proxy.example.com', secret=RAW_SECRET)


def test_mtproxy_apply_requires_auth(client: TestClient) -> None:
    resp = client.put('/mtproxy', json=_payload())

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_mtproxy_status_requires_auth(client: TestClient) -> None:
    resp = client.get('/mtproxy/status')

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_mtproxy_disable_requires_auth(client: TestClient) -> None:
    resp = client.delete('/mtproxy')

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_mtproxy_apply_writes_config_restarts_and_returns_redacted_status(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    calls: list[str] = []

    def supervisor(action: str) -> str:
        calls.append(action)
        return 'mtproxy RUNNING pid 123, uptime 0:00:01'

    with (
        patch.object(agent, 'supervisor_mtproxy', side_effect=supervisor, create=True),
        patch.object(
            mtproxy, 'supervisor_mtproxy', side_effect=lambda action, **_: supervisor(action)
        ),
    ):
        resp = client.put('/mtproxy', json=_payload(), headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'state': 'running',
        'port': 443,
        'public_host': 'proxy.example.com',
        'secret_set': True,
    }
    assert calls == ['status', 'restart', 'status']
    assert json.loads(mtproxy_config_path.read_text()) == _payload()
    assert RAW_SECRET not in resp.text


def test_mtproxy_apply_starts_stopped_supervisor_program(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    calls: list[str] = []

    def supervisor(action: str) -> str:
        calls.append(action)
        match action:
            case 'status' if calls == ['status']:
                return 'mtproxy STOPPED Jun 28 13:00 PM'
            case 'status':
                return 'mtproxy RUNNING pid 123, uptime 0:00:01'
            case 'start':
                return 'mtproxy: started'
            case unexpected:
                raise AssertionError(f'unexpected supervisor action: {unexpected}')

    with (
        patch.object(agent, 'supervisor_mtproxy', side_effect=supervisor, create=True),
        patch.object(
            mtproxy, 'supervisor_mtproxy', side_effect=lambda action, **_: supervisor(action)
        ),
    ):
        resp = client.put('/mtproxy', json=_payload(), headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'state': 'running',
        'port': 443,
        'public_host': 'proxy.example.com',
        'secret_set': True,
    }
    assert calls == ['status', 'start', 'status']
    assert json.loads(mtproxy_config_path.read_text()) == _payload()
    assert RAW_SECRET not in resp.text


def test_mtproxy_apply_writes_config_consumable_by_runtime_wrapper(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    with (
        patch.object(
            agent,
            'supervisor_mtproxy',
            return_value='mtproxy RUNNING pid 123',
            create=True,
        ),
        patch.object(mtproxy, 'supervisor_mtproxy', return_value='mtproxy RUNNING pid 123'),
    ):
        resp = client.put('/mtproxy', json=_payload(), headers=AUTH_HEADERS)

    result = _run_mtproxy_wrapper(mtproxy_config_path.parent, mtproxy_config_path)

    assert resp.status_code == HTTPStatus.OK
    assert result.returncode == 0
    assert 'Dry run: would start mtproto-proxy -u nobody -S <redacted> -M 1 -C 60000' in (
        result.stdout
    )
    assert '--allow-skip-dh' in result.stdout
    assert '-p 8888 -H 443' in result.stdout
    assert '--aes-pwd ' in result.stdout
    assert 'MTProxy disabled by config' not in result.stdout
    assert RAW_SECRET not in result.stdout
    assert RAW_SECRET not in result.stderr


def test_mtproxy_apply_is_idempotent(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    calls: list[str] = []

    def supervisor(action: str) -> str:
        calls.append(action)
        return 'mtproxy RUNNING pid 123, uptime 0:00:01'

    with (
        patch.object(agent, 'supervisor_mtproxy', side_effect=supervisor, create=True),
        patch.object(
            mtproxy, 'supervisor_mtproxy', side_effect=lambda action, **_: supervisor(action)
        ),
    ):
        first = client.put('/mtproxy', json=_payload(), headers=AUTH_HEADERS)
        second = client.put('/mtproxy', json=_payload(), headers=AUTH_HEADERS)

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.OK
    assert second.json() == first.json()
    assert calls == ['status', 'restart', 'status', 'status', 'restart', 'status']
    assert json.loads(mtproxy_config_path.read_text()) == _payload()


def test_mtproxy_status_returns_redacted_state(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    apply_mtproxy_config(MTProxyConfig.model_validate(_payload()), config_path=mtproxy_config_path)

    with patch.object(mtproxy, 'supervisor_mtproxy', return_value='mtproxy RUNNING pid 123'):
        resp = client.get('/mtproxy/status', headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'state': 'running',
        'port': 443,
        'public_host': 'proxy.example.com',
        'secret_set': True,
    }
    assert RAW_SECRET not in resp.text


def test_mtproxy_status_uses_disabled_for_stale_config_when_supervisor_missing(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    apply_mtproxy_config(MTProxyConfig.model_validate(_payload()), config_path=mtproxy_config_path)

    with patch.object(
        mtproxy,
        'supervisor_mtproxy',
        side_effect=SupervisorCommandError('status', 3),
    ):
        resp = client.get('/mtproxy/status', headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'state': 'disabled',
        'port': 443,
        'public_host': 'proxy.example.com',
        'secret_set': True,
    }


def test_mtproxy_disable_stops_and_removes_config(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    apply_mtproxy_config(MTProxyConfig.model_validate(_payload()), config_path=mtproxy_config_path)
    calls: list[str] = []

    def supervisor(action: str) -> str:
        calls.append(action)
        return 'mtproxy STOPPED Jun 26 10:00 AM'

    with patch.object(agent, 'supervisor_mtproxy', side_effect=supervisor, create=True):
        resp = client.delete('/mtproxy', headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {
        'state': 'disabled',
        'port': None,
        'public_host': None,
        'secret_set': False,
    }
    assert calls == ['stop']
    assert not mtproxy_config_path.exists()

    result = _run_mtproxy_wrapper(mtproxy_config_path.parent, mtproxy_config_path)

    assert result.returncode == 0
    assert 'Config not found' in result.stdout
    assert RAW_SECRET not in result.stdout
    assert RAW_SECRET not in result.stderr


def test_mtproxy_wrapper_exits_cleanly_for_disabled_json_config(tmp_path: Path) -> None:
    config_dir = tmp_path / 'mtproxy'
    config_dir.mkdir()
    config_path = config_dir / 'config.json'
    config_path.write_text('{"enabled": false}\n')

    result = _run_mtproxy_wrapper(config_dir, config_path)

    assert result.returncode == 0
    assert 'MTProxy disabled by config; exiting.' in result.stdout
    assert RAW_SECRET not in result.stdout
    assert RAW_SECRET not in result.stderr


def test_mtproxy_wrapper_rejects_malformed_json_without_secret_leak(tmp_path: Path) -> None:
    config_dir = tmp_path / 'mtproxy'
    config_dir.mkdir()
    config_path = config_dir / 'config.json'
    config_path.write_text(f'{{"port": 443, "secret": "{RAW_SECRET}"')

    result = _run_mtproxy_wrapper(config_dir, config_path)

    assert result.returncode == 1
    assert 'Invalid MTProxy JSON config.' in result.stdout
    assert RAW_SECRET not in result.stdout
    assert RAW_SECRET not in result.stderr


def test_mtproxy_wrapper_falls_back_to_public_ip_when_localhost_resolves_to_loopback(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / 'mtproxy'
    config_dir.mkdir()
    config_path = config_dir / 'config.json'
    config_path.write_text(
        '{"enabled": true, "port": 443, "secret": "0123456789abcdef0123456789abcdef"}\n'
    )

    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    curl_log = tmp_path / 'curl.log'
    curl_path = bin_dir / 'curl'
    curl_path.write_text('#!/bin/sh\nprintf "%s\n" "$*" >> "${CURL_LOG}"\nprintf "95.85.230.107"\n')
    curl_path.chmod(0o755)

    result = _run_mtproxy_wrapper_with_path(
        config_dir,
        config_path,
        bin_dir,
        {
            'CURL_LOG': str(curl_log),
            'MTPROXY_PUBLIC_HOST': 'localhost',
            'MTPROXY_NAT_INTERNAL_IP': '172.19.0.2',
        },
    )

    assert result.returncode == 0
    assert 'Dry run: would start mtproto-proxy -u nobody -S <redacted> -M 1 -C 60000 ' in (
        result.stdout
    )
    assert curl_log.read_text().count('https://api.ipify.org') == 1


@pytest.mark.parametrize(
    'payload',
    [
        {'port': 0, 'public_host': 'proxy.example.com', 'secret': RAW_SECRET},
        {'port': 70000, 'public_host': 'proxy.example.com', 'secret': RAW_SECRET},
        {'port': 443, 'public_host': 'proxy.example.com', 'secret': ''},
    ],
)
def test_mtproxy_apply_rejects_invalid_input_without_secret_leak(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    resp = client.put('/mtproxy', json=payload, headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert RAW_SECRET not in resp.text


def test_mtproxy_apply_timeout_error_does_not_leak_secret(
    client: TestClient,
    mtproxy_config_path: Path,
) -> None:
    _ = mtproxy_config_path

    with (
        patch.object(mtproxy, 'supervisor_mtproxy', return_value='mtproxy RUNNING pid 123'),
        patch.object(
            agent,
            'supervisor_mtproxy',
            side_effect=SupervisorTimeoutError(action='restart'),
            create=True,
        ),
    ):
        resp = client.put('/mtproxy', json=_payload(), headers=AUTH_HEADERS)

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert resp.json() == {'detail': 'supervisorctl restart mtproxy timed out'}
    assert RAW_SECRET not in resp.text


def test_apply_mtproxy_config_writes_restrictive_json(tmp_path: Path) -> None:
    config_path = tmp_path / 'mtproxy' / 'config.json'
    config = MTProxyConfig(port=443, public_host='proxy.example.com', secret=RAW_SECRET)

    apply_mtproxy_config(config, config_path=config_path)

    payload = json.loads(config_path.read_text())
    mode = stat.S_IMODE(config_path.stat().st_mode)
    assert payload == {'port': 443, 'public_host': 'proxy.example.com', 'secret': RAW_SECRET}
    assert mode == 0o600
    assert not list(config_path.parent.glob('*.tmp'))


def test_remove_mtproxy_config_deletes_existing_config(tmp_path: Path) -> None:
    config_path = tmp_path / 'mtproxy' / 'config.json'
    apply_mtproxy_config(
        MTProxyConfig(port=443, public_host='proxy.example.com', secret=RAW_SECRET),
        config_path=config_path,
    )

    remove_mtproxy_config(config_path=config_path)

    assert not config_path.exists()


def test_supervisor_mtproxy_uses_safe_command() -> None:
    calls: list[list[str]] = []

    def runner(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert timeout == 5.0
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout='mtproxy: started',
            stderr='',
        )

    output = supervisor_mtproxy('start', runner=runner)

    assert output == 'mtproxy: started'
    assert calls == [
        ['supervisorctl', '-c', '/etc/supervisor/conf.d/supervisord.conf', 'start', 'mtproxy']
    ]


def test_supervisor_mtproxy_rejects_failed_command_without_secret() -> None:
    def runner(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        assert timeout == 5.0
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout=f'bad stdout {RAW_SECRET}',
            stderr=f'bad stderr {RAW_SECRET}',
        )

    with pytest.raises(SupervisorCommandError) as exc_info:
        supervisor_mtproxy('restart', runner=runner)

    message = str(exc_info.value)
    assert RAW_SECRET not in message
    assert 'supervisorctl restart mtproxy failed with exit code 1' in message


@pytest.mark.parametrize(
    ('supervisor_output', 'expected'),
    [
        ('mtproxy RUNNING pid 123, uptime 0:00:03', 'running'),
        ('mtproxy STOPPED Jun 26 10:00 AM', 'stopped'),
        ('mtproxy FATAL Exited too quickly', 'failed'),
        ('mtproxy BACKOFF retrying', 'failed'),
    ],
)
def test_parse_mtproxy_status_maps_supervisor_states(
    supervisor_output: str,
    expected: str,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / 'mtproxy' / 'config.json'
    apply_mtproxy_config(
        MTProxyConfig(port=443, public_host='proxy.example.com', secret=RAW_SECRET),
        config_path=config_path,
    )

    status = parse_mtproxy_status(supervisor_output, config_path=config_path)

    assert status.state == expected
    assert status.port == 443
    assert status.public_host == 'proxy.example.com'
    assert status.secret_set is True
    assert RAW_SECRET not in status.model_dump_json()


def test_parse_mtproxy_status_returns_disabled_without_config(tmp_path: Path) -> None:
    status = parse_mtproxy_status('mtproxy RUNNING pid 123', config_path=tmp_path / 'config.json')

    assert status.state == 'disabled'
    assert status.port is None
    assert status.public_host is None
    assert status.secret_set is False


def test_read_mtproxy_status_uses_disabled_when_supervisor_is_missing(tmp_path: Path) -> None:
    config_path = tmp_path / 'mtproxy' / 'config.json'
    apply_mtproxy_config(
        MTProxyConfig(port=443, public_host='proxy.example.com', secret=RAW_SECRET),
        config_path=config_path,
    )

    def runner(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
        assert timeout == 5.0
        return subprocess.CompletedProcess(
            args=args,
            returncode=3,
            stdout='',
            stderr='no such process',
        )

    status = read_mtproxy_status(config_path=config_path, runner=runner)

    assert status.state == 'disabled'
    assert status.port == 443
    assert status.public_host == 'proxy.example.com'
    assert status.secret_set is True
    assert RAW_SECRET not in status.model_dump_json()
