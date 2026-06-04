import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import { useI18n } from 'vue-i18n'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { nodesApi } from '../api/nodes'
import type { Node, User } from '../api/types'
import { usersApi } from '../api/users'
import { makeMockNodes, makeMockUsers, scenarioFromLocation } from '../utils/mockUsers'

export function useUsers() {
  const toast = useToast()
  const confirm = useConfirm()
  const { t } = useI18n()

  const users = ref<User[]>([])
  const allNodes = ref<Node[]>([])
  const loadError = ref<string | null>(null)
  const loading = ref(false)
  const newName = ref('')
  const addingUser = ref(false)
  const scenario = scenarioFromLocation()

  const readyNodes = computed(() =>
    allNodes.value.filter((n) => n.server_public_key && n.server_endpoint),
  )

  async function load() {
    loading.value = true
    loadError.value = null
    try {
      if (scenario) {
        users.value = makeMockUsers(scenario)
        allNodes.value = makeMockNodes()
        return
      }
      const [u, n] = await Promise.all([usersApi.getUsers(), nodesApi.getNodes()])
      if (u) {
        users.value = u
      }
      if (n) allNodes.value = n
    } catch (e: unknown) {
      loadError.value = e instanceof Error ? e.message : t('common.error')
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

  async function addUser() {
    const name = newName.value.trim()
    if (!name) return
    addingUser.value = true
    try {
      if (scenario) {
        const user: User = {
          id: `mock-local-${Date.now()}`,
          name,
          vpn_ip: null,
          is_blocked: false,
          online: false,
          peers: [],
          remnawave: null,
          local_traffic: null,
        }
        users.value = [user, ...users.value]
        newName.value = ''
        toast.add({ severity: 'success', summary: t('toasts.added'), detail: name, life: 3000 })
        return
      }
      const user = await usersApi.addUser(name)
      if (user) {
        user.local_traffic = null
        users.value.push(user)
        newName.value = ''
        toast.add({
          severity: 'success',
          summary: t('toasts.added'),
          detail: user.name,
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
      addingUser.value = false
    }
  }

  async function block(user: User) {
    try {
      if (scenario) {
        user.is_blocked = true
        user.peers.forEach((peer) => {
          peer.status = 'pending_delete'
        })
        return
      }
      const updated = await usersApi.blockUser(user.id)
      if (updated) Object.assign(user, updated)
      toast.add({ severity: 'warn', summary: t('toasts.blocked'), detail: user.name, life: 3000 })
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: t('common.error'),
        detail: e instanceof Error ? e.message : t('common.error'),
        life: 4000,
      })
    }
  }

  async function unblock(user: User) {
    try {
      if (scenario) {
        user.is_blocked = false
        user.peers.forEach((peer) => {
          if (peer.status === 'pending_delete') peer.status = 'pending'
        })
        return
      }
      const updated = await usersApi.unblockUser(user.id)
      if (updated) Object.assign(user, updated)
      toast.add({
        severity: 'success',
        summary: t('toasts.unblocked'),
        detail: user.name,
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

  function confirmDelete(event: Event, user: User) {
    confirm.require({
      target: event.currentTarget as HTMLElement,
      message: t('toasts.deleteUserConfirm', { name: user.name }),
      icon: 'pi pi-exclamation-triangle',
      acceptClass: 'p-button-danger',
      acceptLabel: t('toasts.deleteAccept'),
      rejectLabel: t('toasts.deleteReject'),
      accept: () => deleteUser(user),
    })
  }

  async function deleteUser(user: User) {
    try {
      if (scenario) {
        users.value = users.value.filter((u) => u.id !== user.id)
        return
      }
      await usersApi.deleteUser(user.id)
      users.value = users.value.filter((u) => u.id !== user.id)
      toast.add({
        severity: 'success',
        summary: t('toasts.deleted'),
        detail: user.name,
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
    if (scenario) return
    try {
      const [u, n] = await Promise.all([usersApi.getUsers(), nodesApi.getNodes()])
      if (u) {
        users.value = u
      }
      if (n) allNodes.value = n
    } catch {
      /* ignore background errors */
    }
  }

  let pollTimer: ReturnType<typeof setInterval> | null = null

  onMounted(() => {
    pollTimer = setInterval(silentRefresh, 20_000)
  })

  onUnmounted(() => {
    if (pollTimer) clearInterval(pollTimer)
  })

  load()

  return {
    users,
    allNodes,
    loadError,
    loading,
    newName,
    addingUser,
    readyNodes,
    load,
    addUser,
    block,
    unblock,
    confirmDelete,
  }
}
