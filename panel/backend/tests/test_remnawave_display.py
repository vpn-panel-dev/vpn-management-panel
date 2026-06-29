import pytest

from app.services.remnawave_display import derive_remnawave_display


@pytest.mark.parametrize(
    ('description', 'telegram_id', 'display_name', 'telegram_username', 'telegram_url'),
    [
        (
            'Bot user: Надежда Бубнова Гид Москва @nadezda_bubnova',
            None,
            'Надежда Бубнова Гид Москва',
            'nadezda_bubnova',
            'https://t.me/nadezda_bubnova',
        ),
        ('Bot user: Любовь', None, 'Любовь', None, None),
        ('Bot user: Любовь', 517396326, 'Любовь', None, 'tg://user?id=517396326'),
        (
            'Bot user: @nadezda_bubnova',
            None,
            None,
            'nadezda_bubnova',
            'https://t.me/nadezda_bubnova',
        ),
        (
            '  Bot user:   Надежда   Бубнова   @nadezda_bubnova   ',
            None,
            'Надежда Бубнова',
            'nadezda_bubnova',
            'https://t.me/nadezda_bubnova',
        ),
        (
            'Bot user: @first Надежда @last',
            None,
            '@first Надежда',
            'last',
            'https://t.me/last',
        ),
        ('Надежда @nadezda_bubnova', None, None, None, None),
        ('Not bot user: Надежда', 517396326, None, None, 'tg://user?id=517396326'),
        ('Bot user:', 517396326, None, None, 'tg://user?id=517396326'),
        ('', 517396326, None, None, 'tg://user?id=517396326'),
        (None, 517396326, None, None, 'tg://user?id=517396326'),
    ],
)
def test_derive_remnawave_display_when_description_varies(
    description: str | None,
    telegram_id: int | None,
    display_name: str | None,
    telegram_username: str | None,
    telegram_url: str | None,
) -> None:
    # Given: Remnawave bot text and optional stored Telegram ID.

    # When: display metadata is derived for API/UI callers.
    result = derive_remnawave_display(description, telegram_id)

    # Then: only the safe, display-ready fields are returned.
    assert result.display_name == display_name
    assert result.telegram_username == telegram_username
    assert result.telegram_url == telegram_url


def test_derive_remnawave_display_when_telegram_id_fallback_is_used() -> None:
    # Given: no trailing username but a stored Telegram ID exists.
    telegram_id = 517396326

    # When: display metadata is derived.
    result = derive_remnawave_display('Bot user: Любовь', telegram_id)

    # Then: the fallback is a Telegram deep link, never a username web link.
    assert result.telegram_username is None
    assert result.telegram_url == 'tg://user?id=517396326'
    assert result.telegram_url != 'https://t.me/517396326'
