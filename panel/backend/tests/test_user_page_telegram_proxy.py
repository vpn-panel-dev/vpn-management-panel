from __future__ import annotations

from app.models import Node, TelegramProxyNodeState, TelegramProxySettings, User
from app.mtproxy_secret_crypto import encrypt


async def test_public_user_info_uses_configured_tls_domain(client, db, monkeypatch):
    monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')

    user = User(name='alice')
    node = Node(
        id='node-telegram',
        name='telegram-node',
        url='http://node-agent:8000',
        token='node-token',  # noqa: S106
    )
    settings = TelegramProxySettings(
        enabled=True,
        port=8443,
        tls_domain='proxy.example.net',
        secret_encrypted=encrypt('0123456789abcdef0123456789abcdef'),
        primary_node_id=node.id,
    )
    state = TelegramProxyNodeState(
        node_id=node.id,
        status='ready',
        public_host='proxy.example.com',
        public_port=8443,
    )
    db.add_all([user, node, settings, state])
    await db.commit()

    response = await client.get(f'/pub/u/{user.id}/info')

    assert response.status_code == 200
    data = response.json()
    assert data['telegram_proxy']['tg_url'].endswith(
        'secret=ee0123456789abcdef0123456789abcdef70726f78792e6578616d706c652e6e6574'
    )
    assert data['telegram_proxy']['https_url'].endswith(
        'secret=ee0123456789abcdef0123456789abcdef70726f78792e6578616d706c652e6e6574'
    )
