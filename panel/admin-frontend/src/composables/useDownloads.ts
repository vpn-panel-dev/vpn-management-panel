import { reactive } from 'vue'
import { useToast } from 'primevue/usetoast'
import { operationsApi } from '../api/operations'
import type { User, Node, TrafficPoint } from '../api/types'

export interface QrDialog {
  visible: boolean
  title: string
  srcWg: string
  srcAmnezia: string
  tab: 'wg' | 'amnezia'
}

export interface TrafficDialog {
  visible: boolean
  title: string
  loading: boolean
  data: TrafficPoint[] | null
  maxVal: number
}

export const qrTabs = [
  { key: 'wg' as const, label: 'AmneziaWG' },
  { key: 'amnezia' as const, label: 'AmneziaVPN' },
]

export function useDownloads() {
  const toast = useToast()

  const qrDialog = reactive<QrDialog>({
    visible: false,
    title: '',
    srcWg: '',
    srcAmnezia: '',
    tab: 'wg',
  })

  const trafficDialog = reactive<TrafficDialog>({
    visible: false,
    title: '',
    loading: false,
    data: null,
    maxVal: 0,
  })

  async function showQr(user: User, node: Node) {
    if (qrDialog.srcWg) URL.revokeObjectURL(qrDialog.srcWg)
    if (qrDialog.srcAmnezia) URL.revokeObjectURL(qrDialog.srcAmnezia)
    qrDialog.title = `QR — ${user.name} / ${node.name}`
    qrDialog.srcWg = ''
    qrDialog.srcAmnezia = ''
    qrDialog.tab = 'wg'
    qrDialog.visible = true
    try {
      const [wgBlob, amneziaBlob] = await Promise.all([
        operationsApi.fetchQr(user.id, node.id),
        operationsApi.fetchQrAmnezia(user.id, node.id),
      ])
      if (wgBlob) qrDialog.srcWg = URL.createObjectURL(wgBlob)
      if (amneziaBlob) qrDialog.srcAmnezia = URL.createObjectURL(amneziaBlob)
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
      qrDialog.visible = false
    }
  }

  function triggerDownload(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  async function downloadConfig(user: User, node: Node) {
    try {
      const blob = await operationsApi.fetchConfig(user.id, node.id)
      if (blob) triggerDownload(blob, `${user.name}-${node.name}.conf`)
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
    }
  }

  async function downloadConfigZip(user: User) {
    try {
      const blob = await operationsApi.fetchConfigZip(user.id)
      if (blob) triggerDownload(blob, `${user.name}-configs.zip`)
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
    }
  }

  function copyUserLink(user: User) {
    const url = `${window.location.origin}/u/${user.id}`
    navigator.clipboard.writeText(url).then(() => {
      toast.add({ severity: 'success', summary: 'Ссылка скопирована', detail: url, life: 3000 })
    })
  }

  async function showTraffic(user: User) {
    trafficDialog.title = `Трафик — ${user.name}`
    trafficDialog.data = null
    trafficDialog.loading = true
    trafficDialog.visible = true
    try {
      const points = await operationsApi.getUserTraffic(user.id, 30)
      if (points) {
        trafficDialog.maxVal = points.reduce((m, p) => Math.max(m, p.rx_bytes, p.tx_bytes), 0)
        trafficDialog.data = points
      }
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
      trafficDialog.visible = false
    } finally {
      trafficDialog.loading = false
    }
  }

  return {
    qrDialog,
    trafficDialog,
    qrTabs,
    showQr,
    downloadConfig,
    downloadConfigZip,
    copyUserLink,
    showTraffic,
  }
}
