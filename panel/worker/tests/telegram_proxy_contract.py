MTPROXY_TEST_KEY = '0123456789abcdef0123456789abcdef'

EXPECTED_TELEGRAM_PROXY_APPLY_COMMAND_PAYLOAD = {
    'command': 'telegram_proxy_apply_node',
    'idempotency_key': 'idem-telegram-proxy-apply',
    'operation_id': 'op-telegram-proxy-apply',
    'track_operation': True,
    'target_type': 'telegram_proxy_node',
    'target_id': 'node-1',
    'created_at': '2026-06-27T12:00:00+00:00',
}

EXPECTED_TELEGRAM_PROXY_SNAPSHOT_JSON = {
    'node_id': 'node-1',
    'url': 'http://agent.test/',
    'token': 'node-token',
    'desired': {
        'enabled': True,
        'secret': MTPROXY_TEST_KEY,
        'port': 443,
        'public_host': 'proxy.example.com',
    },
}

EXPECTED_TELEGRAM_PROXY_NODE_CONFIG_JSON = {
    'secret': MTPROXY_TEST_KEY,
    'port': 443,
    'public_host': 'proxy.example.com',
}

EXPECTED_TELEGRAM_PROXY_READY_RESULT_JSON = {
    'status': 'ready',
    'public_host': 'proxy.example.com',
    'public_port': 443,
}

EXPECTED_TELEGRAM_PROXY_DISABLED_RESULT_JSON = {'status': 'disabled'}

EXPECTED_TELEGRAM_PROXY_FAILED_RESULT_JSON = {
    'status': 'failed',
    'error': 'node-agent unavailable',
}
