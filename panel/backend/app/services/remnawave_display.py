import re
from dataclasses import dataclass

BOT_USER_PREFIX = 'Bot user:'
TRAILING_TELEGRAM_HANDLE_RE = re.compile(r'(?P<body>.*?)(?:\s+)?@(?P<username>[A-Za-z0-9_]+)$')


@dataclass(frozen=True, slots=True)
class RemnawaveDisplay:
    display_name: str | None
    telegram_username: str | None
    telegram_url: str | None


def derive_remnawave_display(description: str | None, telegram_id: int | None) -> RemnawaveDisplay:
    text = _description_body(description)
    display_name = text
    telegram_username: str | None = None

    if text is not None:
        match = TRAILING_TELEGRAM_HANDLE_RE.fullmatch(text)
        if match is not None:
            display_name = _collapse_whitespace(match.group('body'))
            telegram_username = match.group('username')

    telegram_url = _telegram_url(telegram_username, telegram_id)
    return RemnawaveDisplay(
        display_name=display_name,
        telegram_username=telegram_username,
        telegram_url=telegram_url,
    )


def _description_body(description: str | None) -> str | None:
    if description is None:
        return None

    text = description.strip()
    if not text.startswith(BOT_USER_PREFIX):
        return None

    return _collapse_whitespace(text.removeprefix(BOT_USER_PREFIX))


def _collapse_whitespace(value: str) -> str | None:
    collapsed = ' '.join(value.split())
    if collapsed == '':
        return None
    return collapsed


def _telegram_url(telegram_username: str | None, telegram_id: int | None) -> str | None:
    if telegram_username is not None:
        return f'https://t.me/{telegram_username}'
    if telegram_id is not None:
        return f'tg://user?id={telegram_id}'
    return None
