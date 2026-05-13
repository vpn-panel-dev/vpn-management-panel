import pytest

from app.crypto import (
    AWGClientConfig,
    _build_amnezia_config_json,
    allocate_ip,
    build_amnezia_qr_chunks,
    build_amnezia_vpn_uri,
    build_client_config,
    generate_keypair,
    generate_psk,
)


def test_generate_keypair_returns_valid_keys():
    priv, pub = generate_keypair()
    assert len(priv) == 44
    assert len(pub) == 44
    assert priv != pub
    # second call should produce different keys
    priv2, pub2 = generate_keypair()
    assert priv2 != priv
    assert pub2 != pub


def test_generate_psk_returns_44_chars():
    psk = generate_psk()
    assert len(psk) == 44


def test_allocate_ip_first_host_is_server():
    ip = allocate_ip(set())
    assert ip == '10.8.0.2'


def test_allocate_ip_skips_used():
    ip = allocate_ip({'10.8.0.2', '10.8.0.3'})
    assert ip == '10.8.0.4'


def test_allocate_ip_exhausted():
    network_size = 254
    used = {f'10.8.0.{i}' for i in range(2, network_size + 2)}
    with pytest.raises(RuntimeError, match='exhausted'):
        allocate_ip(used)


def test_generate_keypair_order():
    # pre-generate keys for both Rounds (run twice, gather keys)
    for _ in range(100):
        priv, pub = generate_keypair()
        assert priv != pub
        assert base64_check(priv) and base64_check(pub)


def base64_check(s: str) -> bool:
    import base64

    try:
        base64.b64decode(s, validate=True)
    except Exception:
        return False
    return True


def test_build_client_config_minimal():
    fake_priv = 'a' * 44
    fake_pub = 'b' * 44
    cfg = build_client_config(
        AWGClientConfig(
            private_key=fake_priv,
            vpn_ip='10.8.0.2',
            node_public_key=fake_pub,
            node_endpoint='1.2.3.4:51820',
        )
    )
    assert '[Interface]' in cfg
    assert f'PrivateKey = {fake_priv}' in cfg
    assert 'Address = 10.8.0.2/32' in cfg
    assert '[Peer]' in cfg
    assert f'PublicKey = {fake_pub}' in cfg
    assert 'Endpoint = 1.2.3.4:51820' in cfg
    assert 'Jc = 4' in cfg
    assert 'Jmin = 40' in cfg


def test_build_client_config_with_psk():
    fake_psk = 'p' * 44
    cfg = build_client_config(
        AWGClientConfig(
            private_key='a' * 44,
            vpn_ip='10.8.0.2',
            node_public_key='b' * 44,
            node_endpoint='1.2.3.4:51820',
            psk_key=fake_psk,
        )
    )
    assert f'PresharedKey = {fake_psk}' in cfg


def test_build_client_config_with_i_params():
    cfg = build_client_config(
        AWGClientConfig(
            private_key='a' * 44,
            vpn_ip='10.8.0.2',
            node_public_key='b' * 44,
            node_endpoint='1.2.3.4:51820',
            i1='val1',
            i2='val2',
        )
    )
    assert 'I1 = val1' in cfg
    assert 'I2 = val2' in cfg


def test_build_amnezia_config_json_returns_valid_json():
    import json

    result = _build_amnezia_config_json(
        AWGClientConfig(
            private_key='a' * 44,
            public_key='b' * 44,
            vpn_ip='10.8.0.2',
            node_public_key='c' * 44,
            node_endpoint='1.2.3.4:51820',
        )
    )
    data = json.loads(result)
    assert data['defaultContainer'] == 'amnezia-awg2'
    assert data['hostName'] == '1.2.3.4'
    assert 'containers' in data
    assert len(data['containers']) == 1
    container = data['containers'][0]['awg']
    assert container['port'] == '51820'
    assert container['last_config'] is not None


def test_build_amnezia_vpn_uri():
    priv, pub = generate_keypair()
    _node_priv, node_pub = generate_keypair()
    uri = build_amnezia_vpn_uri(
        AWGClientConfig(
            private_key=priv,
            public_key=pub,
            vpn_ip='10.8.0.2',
            node_public_key=node_pub,
            node_endpoint='1.2.3.4:51820',
        )
    )
    assert uri.startswith('vpn://')
    assert len(uri) > 10


def test_build_amnezia_qr_chunks():
    priv, pub = generate_keypair()
    _node_priv, node_pub = generate_keypair()
    chunks = build_amnezia_qr_chunks(
        AWGClientConfig(
            private_key=priv,
            public_key=pub,
            vpn_ip='10.8.0.2',
            node_public_key=node_pub,
            node_endpoint='1.2.3.4:51820',
        )
    )
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    for chunk in chunks:
        assert isinstance(chunk, str)
        assert '=' not in chunk  # padding stripped
