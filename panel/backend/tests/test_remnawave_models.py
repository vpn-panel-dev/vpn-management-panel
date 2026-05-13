import os

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    RemnawaveSettings,
    RemnawaveSettingsSchema,
    RemnawaveUser,
    RemnawaveWebhookEvent,
    User,
)
from app.remnawave_crypto import decrypt, encrypt


class TestRemnawaveCrypto:
    def test_encrypt_decrypt_roundtrip(self):
        os.environ['REMNAWAVE_SECRET_KEY'] = 'test-secret-32-bytes-minimum-value'
        plaintext = 'my-secret-api-token'
        ciphertext = encrypt(plaintext)
        assert ciphertext != plaintext
        assert decrypt(ciphertext) == plaintext

    def test_encrypt_decrypt_none(self):
        os.environ['REMNAWAVE_SECRET_KEY'] = 'test-secret-32-bytes-minimum-value'
        assert encrypt(None) is None
        assert decrypt(None) is None

    def test_missing_key_raises(self):
        os.environ.pop('REMNAWAVE_SECRET_KEY', None)
        with pytest.raises(RuntimeError, match='REMNAWAVE_SECRET_KEY'):
            encrypt('foo')
        with pytest.raises(RuntimeError, match='REMNAWAVE_SECRET_KEY'):
            decrypt('foo')

    def test_short_key_raises(self):
        os.environ['REMNAWAVE_SECRET_KEY'] = 'short'
        with pytest.raises(RuntimeError, match='at least 32 characters'):
            encrypt('foo')


class TestRemnawaveSettingsModel:
    async def test_singleton_creation(self, db):
        settings = await RemnawaveSettings.get_settings(db)
        assert settings is not None
        settings2 = await RemnawaveSettings.get_settings(db)
        assert settings2.id == settings.id

    async def test_encrypted_token_not_plaintext_in_db(self, db):
        os.environ['REMNAWAVE_SECRET_KEY'] = 'test-secret-32-bytes-minimum-value'
        plaintext = 'super-secret-token'
        settings = RemnawaveSettings(base_url='https://example.com', api_token=encrypt(plaintext))
        db.add(settings)
        await db.commit()

        result = await db.execute(select(RemnawaveSettings))
        row = result.scalar_one()
        assert row.api_token != plaintext
        assert decrypt(row.api_token) == plaintext

    async def test_schema_exposes_set_booleans_not_secrets(self, db):
        os.environ['REMNAWAVE_SECRET_KEY'] = 'test-secret-32-bytes-minimum-value'
        settings = RemnawaveSettings(
            base_url='https://example.com',
            api_token=encrypt('token-value'),
            webhook_secret=encrypt('secret-value'),
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

        schema = RemnawaveSettingsSchema.from_orm(settings)
        assert schema.api_token_set is True
        assert schema.webhook_secret_set is True
        assert not hasattr(schema, 'api_token')
        assert not hasattr(schema, 'webhook_secret')

    async def test_schema_set_booleans_false_when_empty(self, db):
        settings = RemnawaveSettings(base_url='https://example.com')
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

        schema = RemnawaveSettingsSchema.from_orm(settings)
        assert schema.api_token_set is False
        assert schema.webhook_secret_set is False


class TestRemnawaveUserModel:
    async def test_user_uniqueness(self, db):
        user1 = User(name='alice')
        user2 = User(name='bob')
        db.add_all([user1, user2])
        await db.commit()

        ru1 = RemnawaveUser(
            user_id=user1.id,
            remnawave_uuid='uuid-1',
            username='alice_r',
            status='active',
        )
        db.add(ru1)
        await db.commit()

        ru2 = RemnawaveUser(
            user_id=user1.id,
            remnawave_uuid='uuid-2',
            username='alice_r2',
            status='active',
        )
        db.add(ru2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_remnawave_uuid_uniqueness(self, db):
        user1 = User(name='alice')
        user2 = User(name='bob')
        db.add_all([user1, user2])
        await db.commit()

        ru1 = RemnawaveUser(
            user_id=user1.id,
            remnawave_uuid='same-uuid',
            username='alice_r',
            status='active',
        )
        db.add(ru1)
        await db.commit()

        ru2 = RemnawaveUser(
            user_id=user2.id,
            remnawave_uuid='same-uuid',
            username='bob_r',
            status='active',
        )
        db.add(ru2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()

    async def test_cascade_delete_with_user(self, db):
        user = User(name='charlie')
        db.add(user)
        await db.commit()

        ru = RemnawaveUser(
            user_id=user.id,
            remnawave_uuid='uuid-c',
            username='charlie_r',
            status='active',
        )
        db.add(ru)
        await db.commit()

        await db.delete(user)
        await db.commit()

        result = await db.execute(select(RemnawaveUser).where(RemnawaveUser.user_id == user.id))
        assert result.scalar_one_or_none() is None


class TestRemnawaveWebhookEventModel:
    async def test_event_key_uniqueness(self, db):
        event1 = RemnawaveWebhookEvent(
            event_key='key-1',
            event_type='user.created',
        )
        db.add(event1)
        await db.commit()

        event2 = RemnawaveWebhookEvent(
            event_key='key-1',
            event_type='user.updated',
        )
        db.add(event2)
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


class TestMissingEnvKey:
    async def test_missing_key_fails_before_storing_settings(self, db):
        os.environ.pop('REMNAWAVE_SECRET_KEY', None)
        settings = RemnawaveSettings(base_url='https://example.com', api_token='plain-token')  # noqa: S106
        db.add(settings)
        await db.commit()

        result = await db.execute(select(RemnawaveSettings))
        row = result.scalar_one()
        assert row.api_token == 'plain-token'

        with pytest.raises(RuntimeError, match='REMNAWAVE_SECRET_KEY'):
            decrypt(row.api_token)
