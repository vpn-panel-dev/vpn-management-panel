import base64
import binascii
import fcntl
import logging
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from mtproxy import (
    DEFAULT_CONFIG_PATH as DEFAULT_MTPROXY_CONFIG_PATH,
    MTProxyConfig,
    MTProxyStatus,
    SupervisorAction,
    SupervisorCommandError,
    SupervisorTimeoutError,
    apply_mtproxy_config,
    read_mtproxy_status,
    remove_mtproxy_config,
    supervisor_mtproxy,
)

app = FastAPI(title='AmneziaWG Node Agent')
log = logging.getLogger(__name__)

INTERFACE = os.environ.get('WG_INTERFACE', 'awg0')
_WGQUICK_ONLY = re.compile(
    r'^(Address|PostUp|PostDown|DNS|MTU|Table|PreUp|PreDown|SaveConfig)\s*=', re.IGNORECASE
)
AGENT_TOKEN = os.environ.get('AGENT_TOKEN')
if not AGENT_TOKEN:
    raise RuntimeError('AGENT_TOKEN environment variable is required')
WG_CONFIG = os.environ.get('WG_CONFIG', f'/etc/amnezia/amneziawg/{INTERFACE}.conf')
MTPROXY_CONFIG_PATH = Path(os.environ.get('MTPROXY_CONFIG', str(DEFAULT_MTPROXY_CONFIG_PATH)))
PUBKEY_LEN = 32
AWG_DUMP_PART_COUNT = 8
SUPERVISOR_ACTION_ARG_COUNT = 2

_bearer = HTTPBearer()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={'detail': _http_detail(exc.status_code, exc.detail)},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    messages = [_validation_error_message(error) for error in exc.errors()]
    detail = 'Invalid request'
    if messages:
        joined_messages = '; '.join(messages)
        detail = f'{detail}: {joined_messages}'
    return JSONResponse(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, content={'detail': detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    log.exception('Unhandled API error')
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={'detail': 'Internal server error. Details were written to the server log.'},
    )


def _http_detail(status_code: int, detail: Any) -> str:
    if isinstance(detail, str) and detail:
        return detail
    if detail:
        return str(detail)
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return 'HTTP error'


def _validation_error_message(error: dict[str, Any]) -> str:
    location = _validation_location(error.get('loc'))
    message = str(error.get('msg') or 'Invalid value')
    if location:
        return f'{location}: {message}'
    return message


def _validation_location(location: Any) -> str:
    if not isinstance(location, tuple | list):
        return ''
    visible_parts = [str(part) for part in location if part not in {'body', 'query', 'path'}]
    return '.'.join(visible_parts)


def require_auth(creds: Annotated[HTTPAuthorizationCredentials, Security(_bearer)]) -> None:
    if creds.credentials != AGENT_TOKEN:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail='Invalid token')


Auth = Annotated[None, Depends(require_auth)]


def _supervisor_action(args: list[str]) -> SupervisorAction:
    if len(args) >= SUPERVISOR_ACTION_ARG_COUNT and args[1] in {
        'start',
        'stop',
        'restart',
        'status',
    }:
        return cast(SupervisorAction, args[1])
    raise SupervisorCommandError(action='status', returncode=1)


def _mtproxy_status_runner(
    args: list[str],
    _timeout: float,
) -> subprocess.CompletedProcess[str]:
    output = supervisor_mtproxy(_supervisor_action(args))
    return subprocess.CompletedProcess(args=args, returncode=0, stdout=output, stderr='')


def _mtproxy_status() -> MTProxyStatus:
    return read_mtproxy_status(config_path=MTPROXY_CONFIG_PATH, runner=_mtproxy_status_runner)


def _mtproxy_http_error(exc: SupervisorCommandError | SupervisorTimeoutError) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc))


# ── awg helpers ───────────────────────────────────────────────────────────────


@contextmanager
def _awg():
    try:
        yield
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=e.stderr or str(e),
        ) from e


def run_awg(*args: str) -> str:
    with _awg():
        return subprocess.run(  # noqa: S603
            ['awg', *args],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout


@contextmanager
def _config_lock():
    lock_path = Path(str(WG_CONFIG) + '.lock')
    with lock_path.open('w') as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


_INTERFACE_INT_KEYS = frozenset({'jc', 'jmin', 'jmax', 's1', 's2', 's3', 's4'})


@dataclass(frozen=True)
class TransferData:
    received: str
    sent: str


def _parse_transfer(value: str) -> TransferData | None:
    m = re.match(r'(.+?) received,\s*(.+?) sent', value)
    return TransferData(m.group(1), m.group(2)) if m else None


_INTERFACE_PARSERS: dict[str, Any] = {
    'listening_port': int,
    **dict.fromkeys(_INTERFACE_INT_KEYS, int),
}

_PEER_PARSERS: dict[str, Any] = {
    'allowed_ips': lambda v: [ip.strip() for ip in v.split(',')],
    'transfer': _parse_transfer,
}


def parse_awg_show(output: str) -> dict:
    result: dict = {'interface': {}, 'peers': []}
    current_peer: dict | None = None

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('interface:'):
            current_peer = None
            continue
        if line.startswith('peer:'):
            if current_peer is not None:
                result['peers'].append(current_peer)
            current_peer = {
                'public_key': line.split('peer:', 1)[1].strip(),
                'allowed_ips': [],
                'endpoint': None,
                'latest_handshake': None,
                'transfer_rx': None,
                'transfer_tx': None,
            }
            continue
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        key = key.strip().lower().replace(' ', '_')
        value = value.strip()

        if current_peer is None:
            parser = _INTERFACE_PARSERS.get(key)
            result['interface'][key] = parser(value) if parser else value
        elif key == 'transfer':
            transfer_data = _parse_transfer(value)
            if transfer_data:
                current_peer['transfer_rx'] = transfer_data.received
                current_peer['transfer_tx'] = transfer_data.sent
        else:
            parser = _PEER_PARSERS.get(key)
            current_peer[key] = parser(value) if parser else value

    if current_peer is not None:
        result['peers'].append(current_peer)
    return result


def _configured_peers() -> dict[str, dict[str, Any]]:
    if not Path(WG_CONFIG).exists():
        return {}

    with _config_lock():
        config_text = Path(WG_CONFIG).read_text()

    peers: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    for raw in config_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == '[Peer]':
            if current and current.get('public_key'):
                peers[str(current['public_key'])] = current
            current = {'psk_key': '', 'allowed_ips': []}
            continue
        if current is None or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip().lower()
        value = value.strip()
        if key == 'publickey':
            current['public_key'] = value
        elif key == 'presharedkey':
            current['psk_key'] = value
        elif key == 'allowedips':
            current['allowed_ips'] = [ip.strip() for ip in value.split(',') if ip.strip()]
    if current and current.get('public_key'):
        peers[str(current['public_key'])] = current
    return peers


def _persist_peer(pubkey: str, allowed_ip: str, psk_key: str = '') -> None:
    block = ['\n[Peer]\n', f'PublicKey = {pubkey}\n']
    if psk_key:
        block.append(f'PresharedKey = {psk_key}\n')
    block.append(f'AllowedIPs = {allowed_ip}/32\n')

    with _config_lock():
        config_path = Path(WG_CONFIG)
        if not config_path.exists():
            with config_path.open('w') as f:
                f.writelines(block)
            return

        lines = config_path.read_text().splitlines(keepends=True)
        new_lines: list[str] = []
        peer_buffer: list[str] = []
        peer_pubkey: str | None = None
        replaced = False

        def flush_peer_buffer() -> None:
            nonlocal replaced, peer_buffer, peer_pubkey
            if not peer_buffer:
                return
            if peer_pubkey == pubkey:
                new_lines.extend(block)
                replaced = True
            else:
                new_lines.extend(peer_buffer)
            peer_buffer = []
            peer_pubkey = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[Peer]'):
                flush_peer_buffer()
                peer_buffer = [line]
            elif peer_buffer:
                peer_buffer.append(line)
                if stripped.startswith('PublicKey = '):
                    peer_pubkey = stripped.split('=', 1)[1].strip()
            else:
                new_lines.append(line)

        flush_peer_buffer()

        if not replaced:
            new_lines.extend(block)

        with config_path.open('w') as f:
            f.writelines(new_lines)


def _unpersist_peer(pubkey: str) -> None:
    with _config_lock():
        with Path(WG_CONFIG).open() as f:
            lines = f.readlines()

        new_lines: list[str] = []
        peer_buffer: list[str] = []
        peer_pubkey: str | None = None

        for line in lines:
            stripped = line.strip()
            if stripped.startswith('[Peer]'):
                if peer_buffer and peer_pubkey != pubkey:
                    new_lines.extend(peer_buffer)
                peer_buffer = [line]
                peer_pubkey = None
            elif peer_buffer:
                peer_buffer.append(line)
                if stripped.startswith('PublicKey = '):
                    peer_pubkey = stripped.split('=', 1)[1].strip()
            else:
                new_lines.append(line)

        if peer_buffer and peer_pubkey != pubkey:
            new_lines.extend(peer_buffer)

        with Path(WG_CONFIG).open('w') as f:
            f.writelines(new_lines)


def _split_config_sections(config_text: str) -> tuple[str, str]:
    interface_part, sep, peer_part = config_text.partition('[Peer]')
    if not sep:
        return config_text, ''
    return interface_part, '\n' + sep + peer_part


def _interface_has_key(interface_text: str, key: str) -> bool:
    pattern = re.compile(rf'^{re.escape(key)}\s*=.*$', re.MULTILINE)
    return pattern.search(interface_text) is not None


def _build_interface_block(cfg: InterfaceConfig) -> str:
    interface_block = (
        '[Interface]\n'
        f'PrivateKey = {cfg.private_key}\n'
        f'Address = {cfg.address}\n'
        f'ListenPort = {cfg.listen_port}\n'
        f'Jc = {cfg.jc}\n'
        f'Jmin = {cfg.jmin}\n'
        f'Jmax = {cfg.jmax}\n'
        f'S1 = {cfg.s1}\n'
        f'S2 = {cfg.s2}\n'
        f'S3 = {cfg.s3}\n'
        f'S4 = {cfg.s4}\n'
        f'H1 = {cfg.h1}\n'
        f'H2 = {cfg.h2}\n'
        f'H3 = {cfg.h3}\n'
        f'H4 = {cfg.h4}\n'
    )
    for key, val in (
        ('I1', cfg.i1),
        ('I2', cfg.i2),
        ('I3', cfg.i3),
        ('I4', cfg.i4),
        ('I5', cfg.i5),
    ):
        if val:
            interface_block += f'{key} = {val}\n'
    if cfg.post_up:
        interface_block += f'PostUp = {cfg.post_up}\n'
    if cfg.post_down:
        interface_block += f'PostDown = {cfg.post_down}\n'
    return interface_block


def _live_interface_set_args(
    cfg: InterfaceConfig, private_key_path: str, previous_interface_text: str
) -> list[str]:
    args = [
        'awg',
        'set',
        INTERFACE,
        'private-key',
        private_key_path,
        'listen-port',
        str(cfg.listen_port),
        'jc',
        str(cfg.jc),
        'jmin',
        str(cfg.jmin),
        'jmax',
        str(cfg.jmax),
        's1',
        str(cfg.s1),
        's2',
        str(cfg.s2),
        's3',
        str(cfg.s3),
        's4',
        str(cfg.s4),
        'h1',
        cfg.h1,
        'h2',
        cfg.h2,
        'h3',
        cfg.h3,
        'h4',
        cfg.h4,
    ]
    for key, val in (
        ('i1', cfg.i1),
        ('i2', cfg.i2),
        ('i3', cfg.i3),
        ('i4', cfg.i4),
        ('i5', cfg.i5),
    ):
        if val or _interface_has_key(previous_interface_text, key.upper()):
            args.extend([key, val])
    return args


def _apply_live_interface(cfg: InterfaceConfig, previous_interface_text: str) -> None:
    with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as tf:
        tf.write(cfg.private_key)
        private_key_path = tf.name
    try:
        subprocess.run(  # noqa: S603
            _live_interface_set_args(cfg, private_key_path, previous_interface_text),
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        Path(private_key_path).unlink(missing_ok=True)


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.put('/mtproxy')
def apply_mtproxy(req: MTProxyConfig, _: Auth) -> MTProxyStatus:
    try:
        apply_mtproxy_config(req, config_path=MTPROXY_CONFIG_PATH)
        supervisor_mtproxy('restart')
        return _mtproxy_status()
    except (SupervisorCommandError, SupervisorTimeoutError) as exc:
        raise _mtproxy_http_error(exc) from exc


@app.get('/mtproxy/status')
def mtproxy_status(_: Auth) -> MTProxyStatus:
    try:
        return _mtproxy_status()
    except SupervisorTimeoutError as exc:
        raise _mtproxy_http_error(exc) from exc


@app.delete('/mtproxy')
def disable_mtproxy(_: Auth) -> MTProxyStatus:
    try:
        supervisor_mtproxy('stop')
        remove_mtproxy_config(config_path=MTPROXY_CONFIG_PATH)
    except (SupervisorCommandError, SupervisorTimeoutError) as exc:
        raise _mtproxy_http_error(exc) from exc
    return MTProxyStatus(state='disabled', port=None, public_host=None, secret_set=False)


@app.get('/status')
def status(_: Auth):
    result = parse_awg_show(run_awg('show', INTERFACE))
    configured_peers = _configured_peers()
    for peer in result['peers']:
        configured = configured_peers.get(str(peer.get('public_key') or ''))
        if configured is None:
            continue
        peer['psk_key'] = configured.get('psk_key') or ''
    return result


@app.get('/dump')
def dump(_: Auth):
    """Machine-readable peer stats with Unix timestamps and raw byte counts."""
    output = run_awg('show', INTERFACE, 'dump')
    peers = []
    for line in output.splitlines()[1:]:  # skip interface line
        parts = line.split('\t')
        if len(parts) < AWG_DUMP_PART_COUNT:
            continue
        pubkey, _psk, endpoint, _allowed_ips, last_hs, rx, tx, _keepalive = parts
        peers.append(
            {
                'public_key': pubkey,
                'endpoint': endpoint if endpoint != '(none)' else None,
                'last_handshake': int(last_hs),
                'rx_bytes': int(rx),
                'tx_bytes': int(tx),
            }
        )
    return {'peers': peers}


class InterfaceConfig(BaseModel):
    private_key: str
    address: str = '10.8.0.1/24'
    listen_port: int = 51820
    jc: int = 4
    jmin: int = 40
    jmax: int = 70
    s1: int = 0
    s2: int = 0
    s3: int = 0
    s4: int = 0
    h1: str = '1'
    h2: str = '2'
    h3: str = '3'
    h4: str = '4'
    i1: str = ''
    i2: str = ''
    i3: str = ''
    i4: str = ''
    i5: str = ''
    post_up: str = ''
    post_down: str = ''


@app.put('/interface')
def configure_interface(cfg: InterfaceConfig, _: Auth):
    """Write interface config and apply live if interface is already up."""
    interface_block = _build_interface_block(cfg)
    existing = ''
    existing_interface = ''
    peer_tail = ''
    with _config_lock():
        if Path(WG_CONFIG).exists():
            with Path(WG_CONFIG).open() as f:
                existing = f.read()
            existing_interface, peer_tail = _split_config_sections(existing)

        desired = interface_block + peer_tail
        if existing == desired:
            return {'status': 'configured'}

        with Path(WG_CONFIG).open('w') as f:
            f.write(desired)

    # Apply live; silently ignore if interface is not up yet (entrypoint handles bring-up).
    with suppress(subprocess.CalledProcessError):
        _apply_live_interface(cfg, existing_interface)

    return {'status': 'configured'}


class SyncPeerRequest(BaseModel):
    public_key: str
    allowed_ip: str
    psk_key: str | None = None


@app.put('/peers')
def sync_peer(req: SyncPeerRequest, _: Auth):
    """Idempotently ensure a peer exists on the interface."""
    run_awg('show', INTERFACE)

    if req.psk_key:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.psk', delete=False) as tf:
            tf.write(req.psk_key)
            psk_file = tf.name
        try:
            run_awg(
                'set',
                INTERFACE,
                'peer',
                req.public_key,
                'preshared-key',
                psk_file,
                'allowed-ips',
                f'{req.allowed_ip}/32',
            )
        finally:
            Path(psk_file).unlink()
    else:
        run_awg('set', INTERFACE, 'peer', req.public_key, 'allowed-ips', f'{req.allowed_ip}/32')

    _persist_peer(req.public_key, req.allowed_ip, req.psk_key or '')
    return {'status': 'ok'}


@app.delete('/peers/{pubkey_b64}')
def delete_peer(pubkey_b64: str, _: Auth):
    try:
        raw = base64.urlsafe_b64decode(pubkey_b64 + '=' * (-len(pubkey_b64) % 4))
    except binascii.Error as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail='Invalid pubkey encoding'
        ) from e
    if len(raw) != PUBKEY_LEN:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail='Invalid pubkey length')
    pub_std = base64.b64encode(raw).decode()

    run_awg('set', INTERFACE, 'peer', pub_std, 'remove')
    _unpersist_peer(pub_std)
    return {'removed': pub_std}
