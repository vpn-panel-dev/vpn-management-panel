import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta


PANEL_URL = os.environ['PANEL_URL'].rstrip('/')
ADMIN_PASSWORD = os.environ['ADMIN_PASSWORD']
DEMO_NODE_NAME = os.environ.get('DEMO_NODE_NAME', 'Local demo node')
DEMO_NODE_URL = os.environ.get('DEMO_NODE_URL', 'http://node:8000')
DEMO_NODE_TOKEN = os.environ.get('DEMO_NODE_TOKEN', 'test-stand-node-token')
DEMO_NODE_ENDPOINT = os.environ.get('DEMO_NODE_ENDPOINT', '127.0.0.1:51820')
DEMO_USERS = [
    name.strip() for name in os.environ.get('DEMO_USERS', 'alice,bob').split(',') if name.strip()
]
DEMO_BLOCKED_USERS = {
    name.strip()
    for name in os.environ.get('DEMO_BLOCKED_USERS', '').split(',')
    if name.strip()
}
DEMO_NODE_AGENT_URL = os.environ.get('DEMO_NODE_AGENT_URL', 'http://node:8000')
REMNA_BASE_URL = os.environ.get('REMNA_BASE_URL', 'http://remna:8080')
REMNA_PUBLIC_BASE_URL = os.environ.get('REMNA_PUBLIC_BASE_URL', REMNA_BASE_URL)
REMNA_HEALTH_URL = os.environ.get('REMNA_HEALTH_URL', f'{REMNA_BASE_URL}/api/system/health')
REMNA_ADMIN_USERNAME = os.environ.get('REMNA_ADMIN_USERNAME', 'admin')
REMNA_ADMIN_PASSWORD = os.environ.get('REMNA_ADMIN_PASSWORD', 'TestStandRemnawaveAdmin123')
REMNA_API_TOKEN_NAME = os.environ.get('REMNA_API_TOKEN_NAME', 'amnezia-test-stand')
REMNA_WEBHOOK_SECRET = os.environ.get('REMNA_WEBHOOK_SECRET', 'test-stand-remna-webhook-secret')
REMNA_EXPECTED_USERS = int(os.environ.get('REMNA_EXPECTED_USERS', '3'))

REMNA_USERS = [
    {
        'uuid': '11111111-1111-4111-8111-111111111111',
        'username': 'remna-alice',
        'status': 'ACTIVE',
        'email': 'remna-alice@example.test',
        'tag': 'TEST_STAND',
        'trafficLimitBytes': 1_000_000_000,
        'trafficLimitStrategy': 'NO_RESET',
    },
    {
        'uuid': '22222222-2222-4222-8222-222222222222',
        'username': 'remna-bob',
        'status': 'ACTIVE',
        'email': 'remna-bob@example.test',
        'tag': 'TEST_STAND',
        'trafficLimitBytes': 1_500_000_000,
        'trafficLimitStrategy': 'NO_RESET',
    },
    {
        'uuid': '33333333-3333-4333-8333-333333333333',
        'username': 'remna-disabled',
        'status': 'DISABLED',
        'email': 'remna-disabled@example.test',
        'tag': 'TEST_STAND',
        'trafficLimitBytes': 2_000_000_000,
        'trafficLimitStrategy': 'NO_RESET',
    },
]


def request(method: str, path: str, token: str | None = None, payload: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'{PANEL_URL}{path}', data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        body = response.read()
        if not body:
            return None
        return json.loads(body.decode())


def remna_request(
    method: str,
    path: str,
    token: str | None = None,
    payload: dict | None = None,
):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {'Content-Type': 'application/json', 'X-Remnawave-Client-Type': 'browser'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(
        f'{REMNA_BASE_URL.rstrip("/")}{path}',
        data=data,
        headers=headers,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        body = response.read()
        if not body:
            return None
        return json.loads(body.decode())


def response_data(payload):
    if isinstance(payload, dict) and 'response' in payload:
        return payload['response']
    return payload


def login() -> str:
    response = request('POST', '/api/auth/login', payload={'password': ADMIN_PASSWORD})
    return response['token']


def wait_for_panel() -> str:
    last_error = None
    for _ in range(60):
        try:
            return login()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f'Panel did not become ready: {last_error}')


def wait_for_remnawave() -> None:
    last_error = None
    for _ in range(90):
        try:
            with urllib.request.urlopen(REMNA_HEALTH_URL, timeout=10) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f'Remnawave did not become ready: {last_error}')


def remnawave_admin_token() -> str:
    last_error = None
    for _ in range(60):
        try:
            return _remnawave_admin_token_once()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, http.client.RemoteDisconnected) as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f'Remnawave auth did not become ready: {last_error}')


def _remnawave_admin_token_once() -> str:
    try:
        registered = remna_request(
            'POST',
            '/api/auth/register',
            payload={'username': REMNA_ADMIN_USERNAME, 'password': REMNA_ADMIN_PASSWORD},
        )
        print('Registered Remnawave superadmin')
        return response_data(registered)['accessToken']
    except urllib.error.HTTPError as exc:
        if exc.code not in {400, 403, 409}:
            raise

    logged_in = remna_request(
        'POST',
        '/api/auth/login',
        payload={'username': REMNA_ADMIN_USERNAME, 'password': REMNA_ADMIN_PASSWORD},
    )
    print('Logged in to Remnawave')
    return response_data(logged_in)['accessToken']


def create_remnawave_api_token(admin_token: str) -> str:
    token = remna_request(
        'POST',
        '/api/tokens',
        admin_token,
        {'tokenName': REMNA_API_TOKEN_NAME},
    )
    print('Created Remnawave API token for Amnezia')
    return response_data(token)['token']


def get_remnawave_user(username: str, token: str):
    try:
        payload = remna_request('GET', f'/api/users/by-username/{username}', token)
        return response_data(payload)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def ensure_remnawave_users(admin_token: str) -> None:
    expire_at = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    for user in REMNA_USERS:
        username = str(user['username'])
        status = str(user['status'])
        existing = get_remnawave_user(username, admin_token)
        if existing is None:
            payload = dict(user, expireAt=expire_at)
            created = remna_request('POST', '/api/users', admin_token, payload)
            existing = response_data(created)
            print(f'Created Remnawave user: {username}')
        else:
            print(f'Remnawave user already exists: {username}')

        if status == 'DISABLED' and existing.get('status') != 'DISABLED':
            remna_request('POST', f'/api/users/{existing["uuid"]}/actions/disable', admin_token)
            print(f'Disabled Remnawave user: {username}')


def ensure_node(token: str) -> str:
    nodes = request('GET', '/api/nodes', token) or []
    for node in nodes:
        if node['name'] == DEMO_NODE_NAME:
            print(f'Node already exists: {DEMO_NODE_NAME}')
            return node['id']

    node = request(
        'POST',
        '/api/nodes',
        token,
        {
            'name': DEMO_NODE_NAME,
            'url': DEMO_NODE_URL,
            'token': DEMO_NODE_TOKEN,
            'server_endpoint': DEMO_NODE_ENDPOINT,
            'listen_port': 51820,
        },
    )
    print(f'Created node: {DEMO_NODE_NAME}')
    return node['id']


def wait_for_node_agent() -> None:
    last_error = None
    for _ in range(60):
        try:
            url = f'{DEMO_NODE_AGENT_URL.rstrip("/")}/status'
            req = urllib.request.Request(
                url,
                headers={'Authorization': f'Bearer {DEMO_NODE_TOKEN}'},
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    return
        except urllib.error.HTTPError as exc:
            if exc.code == 500:
                return
            last_error = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(f'Node interface did not become ready: {last_error}')


def reprovision_node(token: str, node_id: str) -> None:
    requested = False
    for _ in range(60):
        if not requested:
            request('POST', f'/api/nodes/{node_id}/provision', token)
            print(f'Requested provision retry for node: {DEMO_NODE_NAME}')
            requested = True

        nodes = request('GET', '/api/nodes', token) or []
        node = next((item for item in nodes if item['id'] == node_id), None)
        if node and node['provision_status'] == 'succeeded':
            print(f'Provision succeeded: {DEMO_NODE_NAME}')
            return
        if node and node['provision_status'] == 'failed':
            requested = False
        time.sleep(2)
    raise RuntimeError(f'Provision did not succeed for node: {DEMO_NODE_NAME}')


def enable_remnawave(token: str, remnawave_api_token: str) -> None:
    request(
        'PUT',
        '/api/remnawave/settings',
        token,
        {
            'base_url': REMNA_BASE_URL,
            'enabled': True,
            'polling_enabled': True,
            'polling_interval_seconds': 60,
            'api_token': remnawave_api_token,
            'webhook_secret': REMNA_WEBHOOK_SECRET,
            'subscription_url': f'{REMNA_PUBLIC_BASE_URL}/api/sub',
        },
    )
    print('Remnawave sync is enabled')


def sync_remnawave(token: str) -> None:
    request('POST', '/api/remnawave/test', token)
    request('POST', '/api/remnawave/sync', token)
    for _ in range(60):
        status = request('GET', '/api/remnawave/status', token)
        if int(status['imported_users_count']) >= REMNA_EXPECTED_USERS:
            print(f'Remnawave users imported: {status["imported_users_count"]}')
            return
        time.sleep(2)
    raise RuntimeError('Remnawave sync did not import demo users')


def ensure_users(token: str) -> None:
    users = {user['name']: user for user in request('GET', '/api/users', token) or []}
    for name in DEMO_USERS:
        user = users.get(name)
        if user is None:
            user = request('POST', '/api/users', token, {'name': name})
            print(f'Created user: {name}')
        else:
            print(f'User already exists: {name}')

        if name in DEMO_BLOCKED_USERS and not user['is_blocked']:
            request('PUT', f'/api/users/{user["id"]}/block', token)
            print(f'Blocked user: {name}')


def main() -> int:
    token = wait_for_panel()
    wait_for_remnawave()
    remnawave_admin = remnawave_admin_token()
    ensure_remnawave_users(remnawave_admin)
    remnawave_api_token = create_remnawave_api_token(remnawave_admin)
    node_id = ensure_node(token)
    ensure_users(token)
    wait_for_node_agent()
    reprovision_node(token, node_id)
    enable_remnawave(token, remnawave_api_token)
    sync_remnawave(token)
    print('Test stand seed data is ready')
    return 0


if __name__ == '__main__':
    sys.exit(main())
