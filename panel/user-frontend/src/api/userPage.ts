export interface UserNode {
  id: number
  name: string
  ready: boolean
  vpn_uri?: string
  copied?: boolean
}

export interface UserInfo {
  user_name: string
  blocked: boolean
  nodes: UserNode[]
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
  nodeId: number,
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
