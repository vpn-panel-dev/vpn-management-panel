import pytest

from app.models import Node, TelegramProxyNodeState, TelegramProxySettings
from app.services.telegram_proxy import (
    build_proxy_links,
    generate_proxy_secret,
    normalize_public_host,
    normalize_public_port,
    select_primary_node_state,
    validate_proxy_secret,
)


class TestTelegramProxyLinkGeneration:
    def test_link_generation_is_deterministic_and_url_encoded(self):
        # Given: a fixed public endpoint and MTProxy secret.
        secret = '0123456789abcdef0123456789abcdef'

        # When: links are generated for Telegram clients.
        links = build_proxy_links('vpn.example.com', 443, secret)

        # Then: both link formats use the same encoded query values and order.
        assert links.tg_url == (
            'tg://proxy?server=vpn.example.com&port=443&secret=0123456789abcdef0123456789abcdef'
        )
        assert links.t_me_url == (
            'https://t.me/proxy?server=vpn.example.com&port=443&secret='
            '0123456789abcdef0123456789abcdef'
        )

    def test_link_generation_encodes_host_and_secret(self):
        # Given: a bracketed IPv6 host and dd-prefixed secret accepted by Telegram.
        secret = 'dd0123456789abcdef0123456789abcdef'

        # When: links are generated.
        links = build_proxy_links('[2001:db8::1]', 8443, secret)

        # Then: reserved characters are encoded deterministically.
        assert links.tg_url == (
            'tg://proxy?server=%5B2001%3Adb8%3A%3A1%5D&port=8443&secret='
            'dd0123456789abcdef0123456789abcdef'
        )
        assert links.t_me_url == (
            'https://t.me/proxy?server=%5B2001%3Adb8%3A%3A1%5D&port=8443&secret='
            'dd0123456789abcdef0123456789abcdef'
        )


class TestTelegramProxyInputValidation:
    def test_secret_generation_and_validation_accept_supported_shapes(self):
        # Given / When: generated normal and dd-prefixed secrets are requested.
        normal_secret = generate_proxy_secret()
        padded_secret = generate_proxy_secret(dd_prefixed=True)

        # Then: both are valid MTProxy secret shapes and normalized to lowercase.
        assert validate_proxy_secret(normal_secret) == normal_secret
        assert len(normal_secret) == 32
        assert validate_proxy_secret(padded_secret) == padded_secret
        assert len(padded_secret) == 34
        assert padded_secret.startswith('dd')

    @pytest.mark.parametrize(
        'secret',
        ['not-hex', '0123456789abcdef', 'ee0123456789abcdef0123456789abcdef'],
    )
    def test_invalid_secret_rejects_malformed_input(self, secret: str):
        # Given / When / Then: malformed secret values never produce links.
        with pytest.raises(ValueError, match='secret'):
            validate_proxy_secret(secret)

    @pytest.mark.parametrize('port', [0, 65536, '443'])
    def test_invalid_port_rejects_malformed_input(self, port: object):
        # Given / When / Then: only integer TCP ports are accepted.
        with pytest.raises((TypeError, ValueError), match='port'):
            normalize_public_port(port)

    @pytest.mark.parametrize(
        'host',
        [' vpn.example.com ', 'https://vpn.example.com', 'vpn.example.com:443'],
    )
    def test_public_host_normalization_rejects_ambiguous_hosts(self, host: str):
        # Given / When / Then: host values must already be public hosts, not URLs/endpoints.
        with pytest.raises(ValueError, match='host'):
            normalize_public_host(host)


class TestTelegramProxyPrimaryNodeSelection:
    async def test_primary_node_selection_uses_configured_active_ready_state(self, db):
        # Given: two ready node states but only one configured primary node.
        primary = Node(
            id='primary-node',
            name='primary',
            url='http://private-primary-agent:8000',
            token='token-primary',  # noqa: S106
            server_endpoint='primary-public.example.com:51820',
        )
        secondary = Node(
            id='secondary-node',
            name='secondary',
            url='http://private-secondary-agent:8000',
            token='token-secondary',  # noqa: S106
            server_endpoint='secondary-public.example.com:51820',
        )
        settings = TelegramProxySettings(primary_node_id=primary.id)
        primary_state = TelegramProxyNodeState(
            node_id=primary.id,
            status='ready',
            public_host='primary-public.example.com',
            public_port=443,
        )
        secondary_state = TelegramProxyNodeState(
            node_id=secondary.id,
            status='ready',
            public_host='secondary-public.example.com',
            public_port=443,
        )
        db.add_all([primary, secondary, settings, primary_state, secondary_state])
        await db.commit()

        # When: primary selection runs.
        selected = await select_primary_node_state(db, settings)

        # Then: it returns the configured primary and never an arbitrary first ready node.
        assert selected is primary_state

    async def test_primary_node_selection_returns_none_for_stale_primary_state(self, db):
        # Given: a configured primary node whose state is not ready for public links.
        primary = Node(
            id='primary-node',
            name='primary',
            url='http://private-agent.example:8000',
            token='token-primary',  # noqa: S106
            server_endpoint='primary-public.example.com:51820',
        )
        fallback = Node(
            id='fallback-node',
            name='fallback',
            url='http://private-fallback-agent:8000',
            token='token-fallback',  # noqa: S106
        )
        settings = TelegramProxySettings(primary_node_id=primary.id)
        stale_state = TelegramProxyNodeState(
            node_id=primary.id,
            status='active',
            public_host=None,
            public_port=443,
        )
        fallback_state = TelegramProxyNodeState(
            node_id=fallback.id,
            status='ready',
            public_host='fallback.example.com',
            public_port=443,
        )
        db.add_all([primary, fallback, settings, stale_state, fallback_state])
        await db.commit()

        # When: primary selection runs with a stale configured primary.
        selected = await select_primary_node_state(db, settings)

        # Then: it returns no-link instead of falling back to another node.
        assert selected is None

    async def test_primary_node_selection_returns_none_for_missing_primary_state(self, db):
        # Given: settings point to a primary node that has no stored proxy state yet.
        primary = Node(
            id='primary-node',
            name='primary',
            url='http://private-agent.example:8000',
            token='token-primary',  # noqa: S106
        )
        fallback = Node(
            id='fallback-node',
            name='fallback',
            url='http://private-fallback-agent:8000',
            token='token-fallback',  # noqa: S106
        )
        settings = TelegramProxySettings(primary_node_id=primary.id)
        fallback_state = TelegramProxyNodeState(
            node_id=fallback.id,
            status='ready',
            public_host='fallback.example.com',
            public_port=443,
        )
        db.add_all([primary, fallback, settings, fallback_state])
        await db.commit()

        # When: primary selection runs before the primary state exists.
        selected = await select_primary_node_state(db, settings)

        # Then: it returns no-link and never chooses the fallback state.
        assert selected is None

    async def test_primary_node_selection_returns_none_without_configured_primary(self, db):
        # Given: a ready node exists but settings do not designate it as primary.
        ready_node = Node(
            id='ready-node',
            name='ready',
            url='http://private-ready-agent:8000',
            token='token-ready',  # noqa: S106
        )
        settings = TelegramProxySettings(primary_node_id=None)
        ready_state = TelegramProxyNodeState(
            node_id=ready_node.id,
            status='ready',
            public_host='ready.example.com',
            public_port=443,
        )
        db.add_all([ready_node, settings, ready_state])
        await db.commit()

        # When: primary selection runs without an explicit primary node.
        selected = await select_primary_node_state(db, settings)

        # Then: it returns no-link rather than picking the only ready node.
        assert selected is None
