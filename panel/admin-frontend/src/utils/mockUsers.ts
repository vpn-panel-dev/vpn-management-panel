import type { Node, User } from '../api/types'

const now = Date.now()

export type UserScenario = 'empty' | '3' | '20' | '100' | 'sync-error' | 'blocked-readonly'

export function scenarioFromLocation(): UserScenario | null {
  const params = new URLSearchParams(window.location.search)
  const value = params.get('mockUsers')
  if (
    value === 'empty' ||
    value === '3' ||
    value === '20' ||
    value === '100' ||
    value === 'sync-error' ||
    value === 'blocked-readonly'
  ) {
    return value
  }
  return null
}

export function makeMockNodes(): Node[] {
  return [
    {
      id: 'node-amsterdam',
      name: 'Amsterdam edge',
      url: 'http://10.20.0.2:8000',
      token: 'mock',
      server_endpoint: 'vpn.example.net:51820',
      server_public_key: 'mock-server-public-key-amsterdam',
      listen_port: 51820,
      online: true,
      reachable: true,
      online_peers_count: 12,
      online_threshold_seconds: 180,
      reachability_status: 'reachable',
      last_heartbeat_at: new Date(now - 30_000).toISOString(),
      last_heartbeat_error: null,
      sync_status: 'succeeded',
      sync_error: null,
      last_synced_at: new Date(now - 90_000).toISOString(),
      provision_status: 'succeeded',
      last_error: null,
      jc: 4,
      jmin: 40,
      jmax: 120,
      s1: 88,
      s2: 144,
      s3: 233,
      s4: 377,
      h1: '1',
      h2: '2',
      h3: '3',
      h4: '4',
      i1: null,
      i2: null,
      i3: null,
      i4: null,
      i5: null,
      mtu: '1420',
    },
    {
      id: 'node-singapore',
      name: 'Singapore relay',
      url: 'http://10.21.0.2:8000',
      token: 'mock',
      server_endpoint: 'sg.example.net:51820',
      server_public_key: 'mock-server-public-key-singapore',
      listen_port: 51820,
      online: true,
      reachable: true,
      online_peers_count: 8,
      online_threshold_seconds: 180,
      reachability_status: 'reachable',
      last_heartbeat_at: new Date(now - 45_000).toISOString(),
      last_heartbeat_error: null,
      sync_status: 'succeeded',
      sync_error: null,
      last_synced_at: new Date(now - 120_000).toISOString(),
      provision_status: 'succeeded',
      last_error: null,
      jc: 4,
      jmin: 40,
      jmax: 120,
      s1: 88,
      s2: 144,
      s3: 233,
      s4: 377,
      h1: '1',
      h2: '2',
      h3: '3',
      h4: '4',
      i1: null,
      i2: null,
      i3: null,
      i4: null,
      i5: null,
      mtu: '1420',
    },
  ]
}

export function makeMockUsers(scenario: UserScenario): User[] {
  if (scenario === 'empty') return []
  const count = scenario === '3' ? 3 : scenario === '100' ? 100 : 20
  return Array.from({ length: count }, (_, index) => makeMockUser(index, scenario))
}

function makeMockUser(index: number, scenario: UserScenario): User {
  const n = index + 1
  const remnawave = index % 3 !== 0 || scenario === 'sync-error' || scenario === 'blocked-readonly'
  const blocked = scenario === 'blocked-readonly' ? index % 2 === 0 : index % 11 === 0
  const syncError = scenario === 'sync-error' ? index % 2 === 0 : index % 13 === 0
  const expired = index % 17 === 0
  const expireAt = new Date(now + (index % 9 === 0 ? 5 : 45) * 24 * 60 * 60 * 1000).toISOString()
  const longName = index % 10 === 0 ? '-very-long-operator-name-with-region-and-team' : ''
  const telegramUsername = index % 6 === 0 || index % 2 === 0 ? null : `remnawave_${String(n).padStart(3, '0')}`
  const telegramId = index % 6 === 0 ? null : index % 2 === 0 ? 5_149_087_582 + n : null
  const telegramUrl =
    telegramUsername !== null
      ? `https://t.me/${telegramUsername}`
      : telegramId !== null
        ? `tg://user?id=${telegramId}`
        : null

  return {
    id: `mock-user-${String(n).padStart(3, '0')}`,
    public_token: `mock-token-${String(n).padStart(3, '0')}`,
    name: `${remnawave ? 'rw' : 'local'}-user-${String(n).padStart(3, '0')}${longName}`,
    created_at: new Date(now - n * 24 * 60 * 60 * 1000).toISOString(),
    public_key: `mock-public-key-${n}`,
    vpn_ip: `10.66.${Math.floor(n / 250)}.${(n % 240) + 10}`,
    is_blocked: blocked || expired,
    lifecycle_status: blocked ? 'blocked' : expired ? 'expired' : 'active',
    expire_at: remnawave
      ? null
      : expired
        ? new Date(now - 24 * 60 * 60 * 1000).toISOString()
        : expireAt,
    traffic_limit_bytes: remnawave ? 0 : 50 * 1024 * 1024 * 1024,
    traffic_reset_policy: 'manual',
    traffic_reset_at: null,
    online: index % 4 === 0,
    peers: [
      {
        node_id: 'node-amsterdam',
        node_name: 'Amsterdam edge',
        status: blocked ? 'pending_delete' : 'active',
        last_handshake: index % 4 === 0 ? new Date(now - index * 45_000).toISOString() : null,
        endpoint: index % 4 === 0 ? `198.51.100.${n}:49320` : null,
        online: index % 4 === 0,
      },
      {
        node_id: 'node-singapore',
        node_name: 'Singapore relay',
        status: blocked ? 'pending_delete' : 'active',
        last_handshake: index % 6 === 0 ? new Date(now - index * 60_000).toISOString() : null,
        endpoint: index % 6 === 0 ? `203.0.113.${n}:51120` : null,
        online: index % 6 === 0,
      },
    ],
    local_traffic: {
      source: 'local_amneziawg',
      user_id: `mock-user-${String(n).padStart(3, '0')}`,
      rx_bytes: n * 1024 * 1024 * 13,
      tx_bytes: n * 1024 * 1024 * 7,
      total_bytes: n * 1024 * 1024 * 20,
      updated_at: new Date(now - index * 60_000).toISOString(),
    },
    lifecycle: remnawave
      ? null
      : {
          source: 'local',
          status: blocked ? 'blocked' : expired ? 'expired' : 'active',
          expire_at: expired ? new Date(now - 24 * 60 * 60 * 1000).toISOString() : expireAt,
          traffic_limit_bytes: 50 * 1024 * 1024 * 1024,
          traffic_reset_policy: 'manual',
          traffic_reset_at: null,
          blocked_reason: expired ? 'expired' : blocked ? 'blocked' : null,
        },
    remnawave: remnawave
        ? {
          uuid: `11111111-2222-4${String(index).padStart(3, '0').slice(-3)}-8${String(index).padStart(3, '0').slice(-3)}-aaaaaaaa${String(n).padStart(4, '0')}`,
          username: `remnawave_${String(n).padStart(3, '0')}`,
          display_name: null,
          telegram_username: telegramUsername,
          telegram_url: telegramUrl,
          description: index % 4 === 0 ? null : `Bot user: ${n}`,
          telegram_id: telegramId,
          status: expired ? 'EXPIRED' : blocked ? 'DISABLED' : 'ACTIVE',
          expire_at: expired ? new Date(now - 24 * 60 * 60 * 1000).toISOString() : expireAt,
          email: `user${n}@example.net`,
          tag: index % 5 === 0 ? 'partner' : 'retail',
          traffic_used_bytes: n * 1024 * 1024 * 90,
          traffic_limit_bytes: 100 * 1024 * 1024 * 1024,
          local_amneziawg_traffic_used_bytes: n * 1024 * 1024 * 20,
          combined_traffic_used_bytes: n * 1024 * 1024 * 110,
          blocked_reason: expired ? 'expired' : blocked ? 'disabled' : null,
          delete_requested_at: null,
          last_synced_at: new Date(now - index * 90_000).toISOString(),
          sync_status: syncError ? 'failed' : 'synced',
          sync_reason: syncError ? 'remote lifecycle changed while node sync was queued' : null,
          sync_error: syncError ? 'Remnawave API returned stale subscription metadata' : null,
        }
      : null,
  }
}
