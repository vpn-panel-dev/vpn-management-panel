import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useI18n } from 'vue-i18n'
import { nodesApi } from '../api/nodes'
import type { Node, NodePeer, NodeCreate } from '../api/types'
import { getNodeStage } from '../utils/status'

export type AddForm = NodeCreate

function ri(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function ru32(): number {
  return Math.floor(Math.random() * 4294967296)
}

function randomH(): string {
  return `${ru32()}-${ru32()}`
}

export function randomObfuscation(): Partial<NodeCreate> {
  const jmin = ri(10, 50)
  const s1 = ri(15, 150)
  let s2: number
  do {
    s2 = ri(15, 150)
  } while (s2 === s1 + 56)
  return {
    jc: ri(3, 5),
    jmin,
    jmax: ri(50, 100),
    s1,
    s2,
    s3: ri(15, 150),
    s4: ri(5, 30),
    h1: randomH(),
    h2: randomH(),
    h3: randomH(),
    h4: randomH(),
  }
}

export const defaultForm: NodeCreate = {
  name: '',
  url: '',
  token: '',
  server_endpoint: '',
  jc: 4,
  jmin: 50,
  jmax: 1000,
  s1: 50,
  s2: 50,
  s3: 50,
  s4: 10,
  h1: '1',
  h2: '2',
  h3: '3',
  h4: '4',
}

const nodeStageOrder: Record<ReturnType<typeof getNodeStage>, number> = {
  ready: 0,
  syncing: 1,
  applying_config: 2,
  offline: 3,
  error: 4,
}

function compareText(left: string | null | undefined, right: string | null | undefined): number {
  return (left ?? '').localeCompare(right ?? '', 'ru', { sensitivity: 'base' })
}

function compareNodes(left: Node, right: Node): number {
  const stageDiff = nodeStageOrder[getNodeStage(left)] - nodeStageOrder[getNodeStage(right)]
  if (stageDiff !== 0) return stageDiff

  const nameDiff = compareText(left.name, right.name)
  if (nameDiff !== 0) return nameDiff

  return compareText(left.id, right.id)
}

function sortNodes(items: Node[]): Node[] {
  return [...items].sort(compareNodes)
}

function peerOrder(peer: NodePeer): number {
  if (peer.is_blocked || ['pending_delete', 'deleted', 'failed', 'error'].includes(peer.status))
    return 2
  if (peer.status === 'active') return 0
  if (peer.status === 'pending' || peer.status === 'queued') return 1
  return 2
}

function compareNodePeers(left: NodePeer, right: NodePeer): number {
  const statusDiff = peerOrder(left) - peerOrder(right)
  if (statusDiff !== 0) return statusDiff

  const nameDiff = compareText(left.user_name, right.user_name)
  if (nameDiff !== 0) return nameDiff

  const ipDiff = compareText(left.vpn_ip, right.vpn_ip)
  if (ipDiff !== 0) return ipDiff

  return compareText(left.endpoint, right.endpoint)
}

function sortNodePeers(items: NodePeer[]): NodePeer[] {
  return [...items].sort(compareNodePeers)
}

export function useNodes() {
  const toast = useToast()
  const confirm = useConfirm()
  const { t } = useI18n()

  const nodes = ref<Node[]>([])
  const loading = ref(false)
  const expandedRows = ref<Record<string, boolean>>({})
  const peersCache = reactive<Record<string, NodePeer[] | null>>({})
  const provisioning = reactive<Record<string, boolean>>({})

  const showAdd = ref(false)
  const submitting = ref(false)

  async function loadNodes() {
    loading.value = true
    try {
      const data = await nodesApi.getNodes()
      if (data) nodes.value = sortNodes(data)
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: e instanceof Error ? e.message : t('common.error'),
        life: 4000,
      })
    } finally {
      loading.value = false
    }
  }

  watch(expandedRows, async (rows) => {
    for (const nodeId of Object.keys(rows)) {
      if (rows[nodeId] && !peersCache[nodeId]) {
        peersCache[nodeId] = null
        try {
          const peers = await nodesApi.getNodePeers(nodeId)
          peersCache[nodeId] = sortNodePeers(peers ?? [])
        } catch {
          peersCache[nodeId] = []
        }
      }
    }
  })

  async function provisionNode(node: Node) {
    provisioning[node.id] = true
    try {
      await nodesApi.provisionNode(node.id)
      toast.add({
        severity: 'success',
        summary: t('toasts.configApplied'),
        detail: node.name,
        life: 3000,
      })
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: e instanceof Error ? e.message : t('common.error'),
        life: 4000,
      })
    } finally {
      provisioning[node.id] = false
    }
  }

  function openAdd() {
    showAdd.value = true
  }

  async function addNode(formData: NodeCreate) {
    submitting.value = true
    try {
      const node = await nodesApi.addNode(formData)
      if (node) {
        nodes.value = sortNodes([
          ...nodes.value,
          {
            ...node,
            online: false,
            reachable: false,
            online_peers_count: 0,
            online_threshold_seconds: 180,
          },
        ])
        showAdd.value = false
        toast.add({
          severity: 'success',
          summary: t('toasts.added'),
          detail: node.name,
          life: 3000,
        })
      }
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: e instanceof Error ? e.message : t('common.error'),
        life: 4000,
      })
    } finally {
      submitting.value = false
    }
  }

  function confirmDelete(event: Event, node: Node) {
    confirm.require({
      target: event.currentTarget as HTMLElement,
      message: t('toasts.deleteNodeConfirm', { name: node.name }),
      icon: 'pi pi-exclamation-triangle',
      acceptClass: 'p-button-danger',
      acceptLabel: t('toasts.deleteAccept'),
      rejectLabel: t('toasts.deleteReject'),
      accept: () => deleteNode(node),
    })
  }

  async function deleteNode(node: Node) {
    try {
      await nodesApi.deleteNode(node.id)
      nodes.value = nodes.value.filter((n) => n.id !== node.id)
      toast.add({
        severity: 'success',
        summary: t('toasts.deleted'),
        detail: node.name,
        life: 3000,
      })
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: e instanceof Error ? e.message : t('common.error'),
        life: 4000,
      })
    }
  }

  async function silentRefresh() {
    try {
      const data = await nodesApi.getNodes()
      if (data) nodes.value = sortNodes(data)
      for (const nodeId of Object.keys(expandedRows.value)) {
        if (expandedRows.value[nodeId]) {
          const peers = await nodesApi.getNodePeers(nodeId)
          peersCache[nodeId] = sortNodePeers(peers ?? [])
        }
      }
    } catch {
      /* ignore background errors */
    }
  }

  let pollTimer: ReturnType<typeof setInterval> | null = null
  onMounted(() => {
    pollTimer = setInterval(silentRefresh, 20_000)
    loadNodes()
  })
  onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer)
  })

  return {
    nodes,
    loading,
    expandedRows,
    peersCache,
    provisioning,
    showAdd,
    submitting,
    loadNodes,
    provisionNode,
    openAdd,
    addNode,
    confirmDelete,
    deleteNode,
  }
}
