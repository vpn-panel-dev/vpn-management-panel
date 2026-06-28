export interface UserNode {
  id: string
  name: string
  ready: boolean
  vpn_uri?: string
  copied?: boolean
}

export interface PublicStatus {
  code: 'active' | 'blocked' | 'limited' | 'expired'
  reason: string | null
}

export interface PublicSubscription {
  managed: boolean
  expire_at: string | null
  last_synced_at: string | null
}

export interface PublicTraffic {
  used_bytes: number
  limit_bytes: number | null
  local_used_bytes: number
  remote_used_bytes: number
  updated_at: string | null
}

export interface TelegramProxyInfo {
  enabled: boolean
  primary_node_name: string
  tg_url: string
  https_url: string
  status: string
}

export interface UserInfo {
  user_name: string
  blocked: boolean
  nodes: UserNode[]
  status: PublicStatus
  subscription: PublicSubscription
  traffic: PublicTraffic
  telegram_proxy: TelegramProxyInfo | null
  updated_at: string | null
}

export interface VpnQrState {
  chunks: string[]
  idx: number
}

export interface VpnQrError {
  error: true
}

export type VpnQrData = VpnQrState | VpnQrError | null

export interface QrMapItem {
  hasChunks: boolean
  hasError: boolean
  chunks: string[]
  idx: number
  chunkCount: number
}

export async function fetchUserInfo(userId: string): Promise<UserInfo> {
  const res = await fetch(`/pub/u/${userId}/info`)
  if (res.status === 404) throw new Error('404')
  if (!res.ok) throw new Error(String(res.status))
  const data = (await res.json()) as UserInfo
  data.nodes = data.nodes.map((n) => ({ ...n, copied: false }))
  return data
}

export async function fetchVpnChunks(
  userId: string,
  nodeId: string,
  svgToDataUri: (svg: string) => string,
): Promise<VpnQrData> {
  try {
    const res = await fetch(`/pub/u/${userId}/qr-chunks/vpn/${nodeId}`)
    if (!res.ok) return { error: true }
    const data = (await res.json()) as { chunks: string[] }
    return { chunks: data.chunks.map(svgToDataUri), idx: 0 }
  } catch {
    return { error: true }
  }
}
