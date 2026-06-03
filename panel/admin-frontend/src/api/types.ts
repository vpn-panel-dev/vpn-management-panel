export interface Node {
  id: string
  name: string
  url: string
  token: string
  server_endpoint: string | null
  server_public_key: string | null
  listen_port: number | null
  online: boolean
  online_peers_count: number
  online_threshold_seconds: number
  last_error: string | null
  jc: number
  jmin: number
  jmax: number
  s1: number
  s2: number
  s3: number
  s4: number
  h1: string
  h2: string
  h3: string
  h4: string
  i1: string | null
  i2: string | null
  i3: string | null
  i4: string | null
  i5: string | null
  mtu: string | null
}

export interface Peer {
  node_id: string
  node_name: string
  status: string
  last_handshake: string | null
  endpoint: string | null
  online: boolean
}

export interface RemnawaveUserBrief {
  uuid: string
  username: string
  status: string
  expire_at: string | null
  email: string | null
  tag: string | null
  traffic_used_bytes: number
  traffic_limit_bytes: number
  local_amneziawg_traffic_used_bytes: number
  combined_traffic_used_bytes: number
  blocked_reason: string | null
  delete_requested_at: string | null
  last_synced_at: string | null
  sync_status: string
  sync_reason: string | null
  sync_error: string | null
}

export interface User {
  id: string
  name: string
  created_at?: string
  public_key?: string | null
  vpn_ip: string | null
  is_blocked: boolean
  online: boolean
  peers: Peer[]
  remnawave: RemnawaveUserBrief | null
  local_traffic?: LocalAmneziawgUsageTotals | null
}

export type UserSourceFilter = 'all' | 'local' | 'remnawave'
export type UserStatusFilter = 'all' | 'active' | 'blocked' | 'expired' | 'expiring' | 'sync_issues'
export type UserSortKey = 'name' | 'status' | 'source' | 'traffic' | 'expiration' | 'sync'

export interface UserListQuery {
  search: string
  source: UserSourceFilter
  status: UserStatusFilter
  sort: UserSortKey
  page: number
  pageSize: number
}

export interface UserListFacets {
  total: number
  online: number
  blocked: number
  local: number
  remnawave: number
  syncIssues: number
  expiring: number
}

export interface UserListResponse {
  items: User[]
  total: number
  page: number
  pageSize: number
  facets: UserListFacets
}

export interface TrafficPoint {
  day: string
  rx_bytes: number
  tx_bytes: number
}

export interface LocalAmneziawgUsageTotals {
  source: 'local_amneziawg'
  user_id: string
  rx_bytes: number
  tx_bytes: number
  total_bytes: number
  updated_at: string | null
}

export interface LocalAmneziawgUsageNodeTotals extends LocalAmneziawgUsageTotals {
  node_id: string
  node_name: string
}

export interface LocalAmneziawgNodeUsageTotals {
  source: 'local_amneziawg'
  node_id: string
  node_name: string
  rx_bytes: number
  tx_bytes: number
  total_bytes: number
  updated_at: string | null
}

export interface LocalAmneziawgUsageDailyTotals {
  source: 'local_amneziawg'
  user_id: string
  day: string
  rx_bytes: number
  tx_bytes: number
  total_bytes: number
  updated_at: string | null
}

export interface LocalAmneziawgUsageNodeDailyTotals extends LocalAmneziawgUsageDailyTotals {
  node_id: string
  node_name: string
}

export interface NodePeer {
  endpoint: string | null
  last_handshake: string | null
  online: boolean
  user_name: string
  vpn_ip: string
  status: string
}

export interface LoginResponse {
  token: string
}

export interface NodeCreate {
  name: string
  url: string
  token: string
  server_endpoint: string
  jc: number
  jmin: number
  jmax: number
  s1: number
  s2: number
  s3: number
  s4: number
  h1: string
  h2: string
  h3: string
  h4: string
}

export interface NodeUpdate {
  name?: string
  url?: string
  token?: string
  server_endpoint?: string | null
  jc?: number
  jmin?: number
  jmax?: number
  s1?: number
  s2?: number
  s3?: number
  s4?: number
  h1?: string
  h2?: string
  h3?: string
  h4?: string
  i1?: string
  i2?: string
  i3?: string
  i4?: string
  i5?: string
  mtu?: string
}

export interface RemnawaveSettings {
  id: string
  base_url: string | null
  enabled: boolean
  polling_enabled: boolean
  polling_interval_seconds: number
  api_token_set: boolean
  webhook_secret_set: boolean
  subscription_url: string | null
  last_tested_at: string | null
  last_test_status: string | null
  last_test_error: string | null
  last_synced_at: string | null
  created_at: string
  updated_at: string
}

export interface LocalAmneziawgTrafficSettings {
  id: string
  raw_sample_retention_days: number
  peer_online_threshold_seconds: number
  created_at: string
  updated_at: string
}

export interface LocalAmneziawgTrafficSettingsUpdate {
  raw_sample_retention_days: number
  peer_online_threshold_seconds: number
}

export interface RemnawaveSettingsUpdate {
  base_url?: string
  enabled?: boolean
  polling_enabled?: boolean
  polling_interval_seconds?: number
  api_token?: string
  webhook_secret?: string
  clear_api_token?: boolean
  clear_webhook_secret?: boolean
}

export interface RemnawaveTestResult {
  success: boolean
  error: string | null
}

export interface RemnawaveSyncResult {
  operation_id: string
  status_url: string
}

export interface RemnawaveStatus {
  enabled: boolean
  base_url: string | null
  last_successful_reconcile_at: string | null
  last_failed_reconcile_at: string | null
  last_error: string | null
  imported_users_count: number
  pending_node_sync_count: number
  last_tested_at: string | null
  last_test_status: string | null
  last_test_error: string | null
}
