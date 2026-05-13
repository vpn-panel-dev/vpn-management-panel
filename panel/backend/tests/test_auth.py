from http import HTTPStatus

from httpx import AsyncClient


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
