import { useToast } from 'primevue/usetoast'
import { useI18n } from 'vue-i18n'
import { reactive } from 'vue'
import { operationsApi } from '../api/operations'
import type {
  LocalAmneziawgUsageDailyTotals,
  LocalAmneziawgUsageNodeDailyTotals,
  LocalAmneziawgUsageNodeTotals,
  LocalAmneziawgUsageTotals,
  Node,
  TrafficPoint,
  User,
} from '../api/types'

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
  data: TrafficPoint[]
  maxVal: number
  localTotals: LocalAmneziawgUsageTotals | null
  user: User | null
  localDaily: LocalAmneziawgUsageDailyTotals[]
  localNodes: LocalAmneziawgUsageNodeTotals[]
  localNodesDaily: LocalAmneziawgUsageNodeDailyTotals[]
}

export const qrTabs = [
  { key: 'wg' as const, labelKey: 'qrDialog.amneziaWg' },
  { key: 'amnezia' as const, labelKey: 'qrDialog.amneziaVpn' },
]

export function useDownloads() {
  const toast = useToast()
  const { t } = useI18n()
  const trafficDays = 30
  let trafficRequestId = 0

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
    data: [],
    maxVal: 0,
    localTotals: null,
    user: null,
    localDaily: [],
    localNodes: [],
    localNodesDaily: [],
  })

  async function showQr(user: User, node: Node) {
    if (qrDialog.srcWg) URL.revokeObjectURL(qrDialog.srcWg)
    if (qrDialog.srcAmnezia) URL.revokeObjectURL(qrDialog.srcAmnezia)
    qrDialog.title = `${user.name} / ${node.name}`
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
        summary: t('toasts.error'),
        detail: e instanceof Error ? e.message : t('toasts.error'),
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
        summary: t('toasts.error'),
        detail: e instanceof Error ? e.message : t('toasts.error'),
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
        summary: t('toasts.error'),
        detail: e instanceof Error ? e.message : t('toasts.error'),
        life: 4000,
      })
    }
  }

  function copyUserLink(user: User) {
    const url = `${window.location.origin}/u/${user.id}`
    navigator.clipboard.writeText(url).then(() => {
      toast.add({ severity: 'success', summary: t('toasts.linkCopied'), detail: url, life: 3000 })
    })
  }

  async function showTraffic(user: User) {
    const requestId = ++trafficRequestId
    trafficDialog.title = t('trafficDialog.title', { name: user.name })
    trafficDialog.data = []
    trafficDialog.maxVal = 0
    trafficDialog.localTotals = null
    trafficDialog.user = user
    trafficDialog.localDaily = []
    trafficDialog.localNodes = []
    trafficDialog.localNodesDaily = []
    trafficDialog.loading = true
    trafficDialog.visible = true
    try {
      const [points, localTotals, localDaily, localNodes, localNodesDaily] = await Promise.all([
        operationsApi.getUserTraffic(user.id, trafficDays),
        operationsApi.getUserLocalTraffic(user.id),
        operationsApi.getUserLocalTrafficDaily(user.id, trafficDays),
        operationsApi.getUserLocalTrafficNodes(user.id),
        operationsApi.getUserLocalTrafficNodesDaily(user.id, trafficDays),
      ])

      if (requestId !== trafficRequestId) return

      if (points) {
        trafficDialog.maxVal = points.reduce((m, p) => Math.max(m, p.rx_bytes, p.tx_bytes), 0)
        trafficDialog.data = points
      }
      trafficDialog.localTotals = localTotals ?? null
      trafficDialog.localDaily = localDaily ?? []
      trafficDialog.localNodes = localNodes ?? []
      trafficDialog.localNodesDaily = localNodesDaily ?? []
    } catch (e: unknown) {
      if (requestId !== trafficRequestId) return
      toast.add({
        severity: 'error',
        summary: t('toasts.error'),
        detail: e instanceof Error ? e.message : t('toasts.error'),
        life: 4000,
      })
      trafficDialog.visible = false
    } finally {
      if (requestId === trafficRequestId) {
        trafficDialog.loading = false
      }
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
