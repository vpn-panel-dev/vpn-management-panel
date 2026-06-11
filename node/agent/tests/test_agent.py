import base64
import os
import subprocess
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import agent


def _sample_show_output():
    return """interface: awg0
  public key: Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg+a+LQ4GqFjWk8=
  private key: (hidden)
  listening port: 51820
  jc: 4
  jmin: 40
  jmax: 70
  s1: 0
  s2: 0
  s3: 0
  s4: 0
  h1: 1
  h2: 2
  h3: 3
  h4: 4
  mtu: 1420

peer: abcdefghijklmnopqrstuvwxyz1234567890abcd=
  endpoint: 1.2.3.4:51820
  allowed ips: 10.8.0.2/32
  latest handshake: 1 minute, 30 seconds ago
  transfer: 1.23 MiB received, 456.78 KiB sent

peer: zyxwvutsrqponmlkjihgfedcba0987654321abcd=
  endpoint: 5.6.7.8:51820
  allowed ips: 10.8.0.3/32
  latest handshake: 5 seconds ago
  transfer: 10.00 GiB received, 2.50 GiB sent
"""


def test_parse_awg_show_interface():
    result = agent.parse_awg_show(_sample_show_output())
    iface = result['interface']
    assert iface['public_key'] == 'Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg+a+LQ4GqFjWk8='
    assert iface['listening_port'] == 51820
    assert iface['jc'] == 4
    assert iface['jmin'] == 40
    assert iface['jmax'] == 70
    assert iface['s1'] == 0
    assert iface['s2'] == 0
    assert iface['s3'] == 0
    assert iface['s4'] == 0
    assert iface['h1'] == '1'
    assert iface['h2'] == '2'
    assert iface['h3'] == '3'
    assert iface['h4'] == '4'
    assert iface['mtu'] == '1420'


def test_parse_awg_show_peers():
    result = agent.parse_awg_show(_sample_show_output())
    peers = result['peers']
    assert len(peers) == 2

    assert peers[0]['public_key'] == 'abcdefghijklmnopqrstuvwxyz1234567890abcd='
    assert peers[0]['endpoint'] == '1.2.3.4:51820'
    assert peers[0]['allowed_ips'] == ['10.8.0.2/32']
    assert peers[0]['latest_handshake'] == '1 minute, 30 seconds ago'
    assert peers[0]['transfer_rx'] == '1.23 MiB'
    assert peers[0]['transfer_tx'] == '456.78 KiB'

    assert peers[1]['public_key'] == 'zyxwvutsrqponmlkjihgfedcba0987654321abcd='
    assert peers[1]['endpoint'] == '5.6.7.8:51820'
    assert peers[1]['allowed_ips'] == ['10.8.0.3/32']


def test_parse_awg_show_empty():
    result = agent.parse_awg_show('')
    assert result['interface'] == {}
    assert result['peers'] == []


def test_parse_awg_show_interface_only():
    output = """interface: awg0
  public key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
  listening port: 51820
"""
    result = agent.parse_awg_show(output)
    assert result['interface']['public_key'] == 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
    assert result['interface']['listening_port'] == 51820
    assert result['peers'] == []


def test_parse_awg_show_multiple_allowed_ips():
    output = """interface: awg0
  public key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
  listening port: 51820

peer: Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg+a+LQ4GqFjWk8=
  allowed ips: 10.8.0.2/32, 10.8.0.3/32, 192.168.1.0/24
  transfer: 0 B received, 0 B sent
"""
    result = agent.parse_awg_show(output)
    assert result['peers'][0]['allowed_ips'] == ['10.8.0.2/32', '10.8.0.3/32', '192.168.1.0/24']


# ── Health ──────────────────────────────────────────────────────────────────────


def test_health(client: TestClient):
    resp = client.get('/health')
    assert resp.status_code == HTTPStatus.OK
    assert resp.json() == {'status': 'ok'}


# ── Auth ────────────────────────────────────────────────────────────────────────


def test_status_unauthorized(client: TestClient):
    resp = client.get('/status')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_status_wrong_token(client: TestClient):
    resp = client.get('/status', headers={'Authorization': 'Bearer wrong-token'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_dump_unauthorized(client: TestClient):
    resp = client.get('/dump')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_interface_put_unauthorized(client: TestClient):
    resp = client.put('/interface', json={})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_sync_peer_unauthorized(client: TestClient):
    resp = client.put('/peers', json={})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_delete_peer_unauthorized(client: TestClient):
    resp = client.delete('/peers/Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg--LQ4GqFjWk8')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


# ── Status (with mocked awg) ───────────────────────────────────────────────────


def test_status_authorized(client: TestClient, auth_headers: dict):
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = _sample_show_output()
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.get('/status', headers=auth_headers)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data['interface']['public_key'] == 'Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg+a+LQ4GqFjWk8='
        assert len(data['peers']) == 2


def test_status_awg_error(client: TestClient, auth_headers: dict):
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, 'awg', stderr='device not found')

        resp = client.get('/status', headers=auth_headers)
        assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert 'device not found' in resp.json()['detail']


def test_validation_error_is_human_readable(client: TestClient, auth_headers: dict):
    resp = client.put('/interface', json={}, headers=auth_headers)

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json() == {'detail': 'Invalid request: private_key: Field required'}
    assert 'mozilla.org' not in resp.text


def test_unhandled_error_is_human_readable(auth_headers: dict):
    client = TestClient(agent.app, raise_server_exceptions=False)
    with (
        patch.object(agent, 'parse_awg_show', side_effect=RuntimeError('cannot parse awg output')),
        patch.object(subprocess, 'run') as mock_run,
    ):
        mock_run.return_value.stdout = 'unexpected output'
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.get('/status', headers=auth_headers)

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert resp.json() == {
        'detail': 'Internal server error. Details were written to the server log.'
    }
    assert 'cannot parse awg output' not in resp.text
    assert 'mozilla.org' not in resp.text


# ── Dump (with mocked awg) ─────────────────────────────────────────────────────


def _sample_dump_output():
    return (
        'awg0\n'
        'Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg+a+LQ4GqFjWk8=\t'
        '(none)\t1.2.3.4:51820\t10.8.0.2/32\t1715200000\t1234567890\t987654321\t25\n'
        'zyxwvutsrqponmlkjihgfedcba0987654321abcd=\t'
        'abcpsk=\t5.6.7.8:51820\t10.8.0.3/32\t1715300000\t1000000\t2000000\t0\n'
    )


def test_dump_authorized(client: TestClient, auth_headers: dict):
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = _sample_dump_output()
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.get('/dump', headers=auth_headers)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert len(data['peers']) == 2

        assert data['peers'][0]['public_key'] == 'Y7LZT0pB0tMMR2MBYipxjtY7E3HqJg+a+LQ4GqFjWk8='
        assert data['peers'][0]['endpoint'] == '1.2.3.4:51820'
        assert data['peers'][0]['last_handshake'] == 1715200000
        assert data['peers'][0]['rx_bytes'] == 1234567890
        assert data['peers'][0]['tx_bytes'] == 987654321

        assert data['peers'][1]['endpoint'] == '5.6.7.8:51820'
        assert data['peers'][1]['rx_bytes'] == 1000000


def test_dump_skips_endpoint_none(client: TestClient, auth_headers: dict):
    output = (
        'awg0\nAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='
        '\tpsk=\t(none)\t10.8.0.2/32\t0\t0\t0\t0\n'
    )
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = output
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.get('/dump', headers=auth_headers)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()['peers'][0]['endpoint'] is None


# ── Interface configuration ─────────────────────────────────────────────────────


def test_configure_interface_no_existing_config(client: TestClient, auth_headers: dict):
    """First-time config — no existing file, no live awg."""
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = ''
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.put(
            '/interface',
            json={
                'private_key': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
                'address': '10.8.0.1/24',
                'listen_port': 51820,
            },
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == {'status': 'configured'}

        cfg = os.environ['WG_CONFIG']
        assert Path(cfg).exists()
        with Path(cfg).open() as f:
            content = f.read()
            assert 'PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=' in content
            assert 'Address = 10.8.0.1/24' in content
            assert 'ListenPort = 51820' in content


def test_configure_interface_preserves_peers(client: TestClient, auth_headers: dict):
    """Reconfiguration should keep existing peer blocks."""
    cfg_path = os.environ['WG_CONFIG']
    with Path(cfg_path).open('w') as f:
        f.write(
            '[Interface]\n'
            'PrivateKey = OLDKEY===========================================\n'
            'Address = 10.8.0.1/24\n\n'
            '[Peer]\n'
            'PublicKey = PEERKEY==========================================\n'
            'AllowedIPs = 10.8.0.2/32\n'
        )

    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = ''
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.put(
            '/interface',
            json={'private_key': 'NEWKEY==========================================='},
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK

        with Path(cfg_path).open() as f:
            content = f.read()
            assert 'PrivateKey = NEWKEY===========================================' in content
            assert 'PublicKey = PEERKEY==========================================' in content
            assert 'AllowedIPs = 10.8.0.2/32' in content


def test_configure_interface_live_awg_failure_is_ignored(client: TestClient, auth_headers: dict):
    """Live awg setconf failure should not fail the request."""
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, 'awg', stderr='no device')

        resp = client.put(
            '/interface',
            json={'private_key': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA='},
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == {'status': 'configured'}


def test_configure_interface_with_optional_params(client: TestClient, auth_headers: dict):
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = ''
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.put(
            '/interface',
            json={
                'private_key': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
                'jc': 10,
                'jmin': 50,
                'jmax': 100,
                'i1': 'custom1',
                'i2': 'custom2',
                'h1': 'a-b',
                'h2': 'c-d',
                'post_up': 'iptables -A FORWARD -i awg0 -j ACCEPT',
                'post_down': 'iptables -D FORWARD -i awg0 -j ACCEPT',
            },
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK

        cfg = os.environ['WG_CONFIG']
        with Path(cfg).open() as f:
            content = f.read()
            assert 'Jc = 10' in content
            assert 'Jmin = 50' in content
            assert 'H1 = a-b' in content
            assert 'I2 = custom2' in content
            assert 'PostUp = iptables -A FORWARD -i awg0 -j ACCEPT' in content


# ── Peer sync / delete ─────────────────────────────────────────────────────────


def test_sync_peer_new(client: TestClient, auth_headers: dict):
    status_output = """interface: awg0
  public key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
  listening port: 51820
"""
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = status_output
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.put(
            '/peers',
            json={
                'public_key': 'PEERKEY==========================================',
                'allowed_ip': '10.8.0.2',
            },
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json() == {'status': 'ok'}

        with Path(os.environ['WG_CONFIG']).open() as f:
            content = f.read()
            assert 'PublicKey = PEERKEY==========================================' in content
            assert 'AllowedIPs = 10.8.0.2/32' in content


def test_sync_peer_with_psk(client: TestClient, auth_headers: dict):
    status_output = """interface: awg0
  public key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
  listening port: 51820
"""
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = status_output
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.put(
            '/peers',
            json={
                'public_key': 'PEERKEY==========================================',
                'allowed_ip': '10.8.0.2',
                'psk_key': 'PSKKEY============================================',
            },
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK

        with Path(os.environ['WG_CONFIG']).open() as f:
            content = f.read()
            assert 'PresharedKey = PSKKEY============================================' in content


def test_sync_peer_existing_skips_persist(client: TestClient, auth_headers: dict):
    """If peer already exists on interface, skip file persistence."""
    status_output = """interface: awg0
  public key: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=
  listening port: 51820

peer: PEERKEY==========================================
  allowed ips: 10.8.0.2/32
"""
    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = status_output
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.put(
            '/peers',
            json={
                'public_key': 'PEERKEY==========================================',
                'allowed_ip': '10.8.0.2',
            },
            headers=auth_headers,
        )
        assert resp.status_code == HTTPStatus.OK


def test_delete_peer(client: TestClient, auth_headers: dict):
    """Delete a peer that exists both on interface and in config."""
    raw_key = os.urandom(32)
    pub_std = base64.b64encode(raw_key).decode()
    pubkey_b64 = base64.urlsafe_b64encode(raw_key).decode().rstrip('=')

    cfg_path = os.environ['WG_CONFIG']
    with Path(cfg_path).open('w') as f:
        f.write(
            '[Interface]\n'
            'PrivateKey = AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n'
            'Address = 10.8.0.1/24\n\n'
            f'[Peer]\n'
            f'PublicKey = {pub_std}\n'
            'AllowedIPs = 10.8.0.2/32\n'
        )

    with patch.object(subprocess, 'run') as mock_run:
        mock_run.return_value.stdout = ''
        mock_run.return_value.stderr = ''
        mock_run.return_value.returncode = 0

        resp = client.delete(f'/peers/{pubkey_b64}', headers=auth_headers)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()['removed'] == pub_std

        with Path(cfg_path).open() as f:
            content = f.read()
            assert pub_std not in content


def test_delete_peer_invalid_base64(client: TestClient, auth_headers: dict):
    resp = client.delete('/peers/!!!invalid!!!', headers=auth_headers)
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_delete_peer_wrong_key_length(client: TestClient, auth_headers: dict):
    """Key must decode to exactly 32 bytes."""
    import base64 as b64

    short_key = b64.b64encode(b'\x00' * 16).decode()
    resp = client.delete(f'/peers/{short_key}', headers=auth_headers)
    assert resp.status_code == HTTPStatus.BAD_REQUEST


# ── _persist_peer / _unpersist_peer ─────────────────────────────────────────────


def test_persist_peer_writes_block():
    agent._persist_peer('NEWPEER==========================================', '10.8.0.2')
    with Path(os.environ['WG_CONFIG']).open() as f:
        content = f.read()
        assert 'PublicKey = NEWPEER==========================================' in content
        assert 'AllowedIPs = 10.8.0.2/32' in content


def test_persist_peer_with_psk():
    agent._persist_peer(
        'NEWPEER==========================================',
        '10.8.0.2',
        psk_key='PSKKEY============================================',
    )
    with Path(os.environ['WG_CONFIG']).open() as f:
        content = f.read()
        assert 'PresharedKey = PSKKEY============================================' in content


def test_persist_peer_idempotent():
    """Persisting same peer twice does not duplicate the block."""
    agent._persist_peer('DUPEPEER=========================================', '10.8.0.3')
    agent._persist_peer('DUPEPEER=========================================', '10.8.0.3')
    with Path(os.environ['WG_CONFIG']).open() as f:
        content = f.read()
        assert content.count('PublicKey = DUPEPEER=========================================') == 1


def test_unpersist_peer_removes_block():
    agent._persist_peer('DELPEER==========================================', '10.8.0.4')
    with Path(os.environ['WG_CONFIG']).open() as f:
        assert 'DELPEER' in f.read()

    agent._unpersist_peer('DELPEER==========================================')
    with Path(os.environ['WG_CONFIG']).open() as f:
        content = f.read()
        assert 'DELPEER' not in content


def test_unpersist_peer_keeps_other_peers():
    agent._persist_peer('KEEP1============================================', '10.8.0.5')
    agent._persist_peer('DELETEME=========================================', '10.8.0.6')
    agent._unpersist_peer('DELETEME=========================================')
    with Path(os.environ['WG_CONFIG']).open() as f:
        content = f.read()
        assert 'KEEP1============================================' in content
        assert 'DELETEME' not in content
