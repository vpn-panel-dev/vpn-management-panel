import { computed, onUnmounted, reactive } from 'vue'
import { fetchVpnChunks, type QrMapItem, type UserInfo, type UserNode, type VpnQrData } from '../api/userPage'
import { svgToDataUri } from '../utils/format'

export function useVpnQrChunks(userId: string) {
  const vpnQr = reactive<Record<number, VpnQrData>>({})
  let chunkTimer: ReturnType<typeof setInterval> | null = null

  const qrMap = computed<Record<number, QrMapItem>>(() => {
    const map: Record<number, QrMapItem> = {}
    for (const node of info.value?.nodes || []) {
      const q = vpnQr[node.id]
      if (q && 'chunks' in q) {
        map[node.id] = {
          hasChunks: true,
          hasError: false,
          chunks: q.chunks,
          idx: q.idx,
          chunkCount: q.chunks.length,
        }
      } else if (q && 'error' in q) {
        map[node.id] = { hasChunks: false, hasError: true, chunks: [], idx: 0, chunkCount: 0 }
      } else {
        map[node.id] = { hasChunks: false, hasError: false, chunks: [], idx: 0, chunkCount: 0 }
      }
    }
    return map
  })

  // info is injected from the page via a setter
  const info = reactive<{ value: UserInfo | null }>({ value: null })

  function setInfo(val: UserInfo | null) {
    info.value = val
  }

  async function loadVpnChunks(node: UserNode) {
    if (!node.ready || !node.vpn_uri) return
    if (node.id in vpnQr) return
    vpnQr[node.id] = null
    vpnQr[node.id] = await fetchVpnChunks(userId, node.id, svgToDataUri)
  }

  function fetchAllVpnChunks() {
    if (!info.value) return
    for (const node of info.value.nodes) loadVpnChunks(node)
    startChunkTimer()
  }

  function startChunkTimer() {
    if (chunkTimer) return
    chunkTimer = setInterval(() => {
      for (const nodeId of Object.keys(vpnQr)) {
        const q = vpnQr[Number(nodeId)]
        if (q && 'chunks' in q && q.chunks.length > 1) {
          q.idx = (q.idx + 1) % q.chunks.length
        }
      }
    }, 1500)
  }

  onUnmounted(() => {
    if (chunkTimer) clearInterval(chunkTimer)
  })

  return { vpnQr, qrMap, setInfo, fetchAllVpnChunks }
}
