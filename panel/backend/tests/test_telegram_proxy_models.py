import pytest
from cryptography.fernet import InvalidToken
from sqlalchemy import select

from app.models import (
    Node,
    TelegramProxyNodeState,
    TelegramProxySettings,
    TelegramProxySettingsSchema,
)
from app.mtproxy_secret_crypto import decrypt, encrypt


class TestTelegramProxySecretCrypto:
    def test_encrypt_decrypt_roundtrip_uses_panel_secret_key(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
        monkeypatch.setenv('REMNAWAVE_SECRET_KEY', 'different-remnawave-secret-value')

        plaintext = '0123456789abcdef0123456789abcdef'
        ciphertext = encrypt(plaintext)

        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext

    def test_decrypt_with_remnawave_secret_key_fails(self, monkeypatch: pytest.MonkeyPatch):
        plaintext = 'fedcba9876543210fedcba9876543210'
        monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
        ciphertext = encrypt(plaintext)

        monkeypatch.setenv('SECRET_KEY', 'different-panel-secret-32-byte-value')
        monkeypatch.setenv('REMNAWAVE_SECRET_KEY', 'panel-secret-32-bytes-minimum-value')

        with pytest.raises(InvalidToken):
            decrypt(ciphertext)

    def test_short_panel_secret_key_raises(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv('SECRET_KEY', 'short')

        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            encrypt('0123456789abcdef0123456789abcdef')


class TestTelegramProxySettingsModel:
    async def test_singleton_defaults(self, db):
        settings = await TelegramProxySettings.get_settings(db)
        settings_again = await TelegramProxySettings.get_settings(db)

        assert settings_again.id == settings.id
        assert settings.enabled is False
        assert settings.port == 443
        assert settings.secret_encrypted is None
        assert settings.primary_node_id is None
        assert settings.last_rotation_at is None
        assert settings.last_rotation_error is None
        assert settings.created_at is not None
        assert settings.updated_at is not None

    async def test_schema_exposes_secret_set_not_secret(self, db, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv('SECRET_KEY', 'panel-secret-32-bytes-minimum-value')
        raw_secret = '0123456789abcdef0123456789abcdef'
        settings = TelegramProxySettings(secret_encrypted=encrypt(raw_secret))
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

        schema = TelegramProxySettingsSchema.from_orm(settings)
        dumped = schema.model_dump()

        assert schema.secret_set is True
        assert 'secret' not in dumped
        assert 'secret_encrypted' not in dumped
        assert raw_secret not in str(dumped)


class TestTelegramProxyNodeStateModel:
    async def test_node_state_defaults_and_node_relationship(self, db):
        node = Node(id='node-telegram', name='node', url='http://node:8000', token='token')  # noqa: S106
        db.add(node)
        await db.commit()

        state = TelegramProxyNodeState(node_id=node.id)
        db.add(state)
        await db.commit()

        row = await db.scalar(
            select(TelegramProxyNodeState).where(TelegramProxyNodeState.node_id == node.id)
        )

        assert row is not None
        assert row.status == 'unknown'
        assert row.public_host is None
        assert row.public_port is None
        assert row.last_applied_at is None
        assert row.last_checked_at is None
        assert row.last_error is None


def test_user_model_has_no_telegram_proxy_secret_fields():
    from app.models import User

    user_columns = set(User.__table__.columns.keys())

    assert 'telegram_proxy_secret' not in user_columns
    assert 'mtproxy_secret' not in user_columns
    assert 'telegram_proxy_secret_encrypted' not in user_columns
