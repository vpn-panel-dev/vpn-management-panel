from http import HTTPStatus
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_login_with_valid_password(client: AsyncClient):
    resp = await client.post('/api/auth/login', json={'password': 'testpass'})
    assert resp.status_code == HTTPStatus.OK
    assert 'token' in resp.json()


async def test_login_with_invalid_password(client: AsyncClient):
    resp = await client.post('/api/auth/login', json={'password': 'wrong'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_protected_route_without_token(client: AsyncClient):
    resp = await client.get('/api/nodes')
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_protected_route_with_valid_token(client: AsyncClient):
    login_resp = await client.post('/api/auth/login', json={'password': 'testpass'})
    token = login_resp.json()['token']
    resp = await client.get('/api/nodes', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == HTTPStatus.OK


async def test_protected_route_with_invalid_token(client: AsyncClient):
    resp = await client.get('/api/nodes', headers={'Authorization': 'Bearer invalid'})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


async def test_login_missing_admin_password(client: AsyncClient, monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', '')
    from app.routers import auth

    auth.ADMIN_PASSWORD = ''
    resp = await client.post('/api/auth/login', json={'password': 'anything'})
    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    auth.ADMIN_PASSWORD = 'testpass'


async def test_validation_error_is_human_readable(client: AsyncClient):
    resp = await client.post('/api/auth/login', json={})

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert resp.json() == {'detail': 'Invalid request: password: Field required'}
    assert 'mozilla.org' not in resp.text


async def test_default_http_error_is_human_readable(client: AsyncClient):
    resp = await client.get('/pub/u/no-such-token/info')

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.json() == {'detail': 'Not Found'}
    assert 'mozilla.org' not in resp.text


async def test_unhandled_error_is_human_readable():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        with patch('app.routers.auth.jwt.encode', side_effect=RuntimeError('token signing failed')):
            resp = await client.post('/api/auth/login', json={'password': 'testpass'})

    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert resp.json() == {
        'detail': 'Internal server error. Details were written to the server log.'
    }
    assert 'token signing failed' not in resp.text
    assert 'mozilla.org' not in resp.text
