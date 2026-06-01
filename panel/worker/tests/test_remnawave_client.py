from __future__ import annotations

import httpx
import pytest

from app.remnawave_client import RemnawaveClient, extract_users_page, normalize_user_payload


@pytest.mark.asyncio
async def test_list_users_uses_bearer_auth_and_normalized_base_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'users': [], 'total': 0})

    client = RemnawaveClient(
        'https://remnawave.test/',
        'secret-token',
        transport=httpx.MockTransport(handler),
    )

    payload = await client.list_users(start=25, size=25)

    assert payload == {'users': [], 'total': 0}
    assert requests[0].url == 'https://remnawave.test/api/users?start=25&size=25'
    assert requests[0].headers['authorization'] == 'Bearer secret-token'


@pytest.mark.asyncio
async def test_get_user_returns_none_on_404() -> None:
    client = RemnawaveClient(
        'https://remnawave.test',
        'secret-token',
        transport=httpx.MockTransport(lambda _request: httpx.Response(404)),
    )

    assert await client.get_user('user-uuid') is None


@pytest.mark.asyncio
async def test_get_user_raises_for_unauthorized() -> None:
    client = RemnawaveClient(
        'https://remnawave.test',
        'secret-token',
        transport=httpx.MockTransport(lambda _request: httpx.Response(401, text='bad token')),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_user('user-uuid')


@pytest.mark.asyncio
async def test_disable_user_posts_disable_action() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={'status': 'ok'})

    client = RemnawaveClient(
        'https://remnawave.test',
        'secret-token',
        transport=httpx.MockTransport(handler),
    )

    assert await client.disable_user('user-uuid') == {'status': 'ok'}
    assert requests[0].method == 'POST'
    assert requests[0].url == 'https://remnawave.test/api/users/user-uuid/actions/disable'


def test_extract_users_page_normalizes_users() -> None:
    users, total = extract_users_page(
        {
            'response': {
                'users': [
                    {
                        'uuid': 'remna-1',
                        'id': 7,
                        'shortUuid': 'short-1',
                        'username': 'alice',
                        'status': 'ACTIVE',
                        'trafficLimitBytes': 1024,
                        'trafficUsedBytes': 512,
                    }
                ],
                'total': 1,
            }
        }
    )

    assert total == 1
    assert users == [
        {
            'remnawave_uuid': 'remna-1',
            'remnawave_id': 7,
            'short_uuid': 'short-1',
            'username': 'alice',
            'status': 'ACTIVE',
            'expire_at': None,
            'email': None,
            'tag': None,
            'telegram_id': None,
            'description': None,
            'traffic_limit_bytes': 1024,
            'traffic_limit_strategy': 'NO_RESET',
            'traffic_used_bytes': 512,
            'lifetime_used_traffic_bytes': 0,
            'last_traffic_reset_at': None,
            'online_at': None,
            'first_connected_at': None,
            'last_connected_node_uuid': None,
            'hwid_device_limit': None,
            'external_squad_uuid': None,
            'active_internal_squads': None,
            'subscription_url': None,
            'created_at': None,
            'updated_at': None,
        }
    ]


def test_extract_users_page_rejects_malformed_response() -> None:
    with pytest.raises(TypeError, match='users list is missing'):
        extract_users_page({'response': {'total': 1}})


def test_normalize_user_payload_rejects_missing_uuid() -> None:
    with pytest.raises(ValueError, match='uuid is missing'):
        normalize_user_payload({'user': {'username': 'alice'}})
