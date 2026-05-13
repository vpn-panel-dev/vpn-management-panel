import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { nodesApi } from '../api/nodes'
import { usersApi } from '../api/users'
import type { User, Node } from '../api/types'

export function useUsers() {
  const toast = useToast()
  const confirm = useConfirm()

  const users = ref<User[]>([])
  const allNodes = ref<Node[]>([])
  const loading = ref(false)
  const newName = ref('')
  const addingUser = ref(false)

  const readyNodes = computed(() =>
    allNodes.value.filter((n) => n.server_public_key && n.server_endpoint),
  )

  async function load() {
    loading.value = true
    try {
      const [u, n] = await Promise.all([usersApi.getUsers(), nodesApi.getNodes()])
      if (u) users.value = u
      if (n) allNodes.value = n
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
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
      const user = await usersApi.addUser(name)
      if (user) {
        users.value.push(user)
        newName.value = ''
        toast.add({ severity: 'success', summary: 'Добавлен', detail: user.name, life: 3000 })
      }
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
    } finally {
      addingUser.value = false
    }
  }

  async function block(user: User) {
    try {
      const updated = await usersApi.blockUser(user.id)
      if (updated) Object.assign(user, updated)
      toast.add({ severity: 'warn', summary: 'Заблокирован', detail: user.name, life: 3000 })
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
    }
  }

  async function unblock(user: User) {
    try {
      const updated = await usersApi.unblockUser(user.id)
      if (updated) Object.assign(user, updated)
      toast.add({ severity: 'success', summary: 'Разблокирован', detail: user.name, life: 3000 })
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
    }
  }

  function confirmDelete(event: Event, user: User) {
    confirm.require({
      target: event.currentTarget as HTMLElement,
      message: `Удалить пользователя «${user.name}»?`,
      icon: 'pi pi-exclamation-triangle',
      acceptClass: 'p-button-danger',
      acceptLabel: 'Удалить',
      rejectLabel: 'Отмена',
      accept: () => deleteUser(user),
    })
  }

  async function deleteUser(user: User) {
    try {
      await usersApi.deleteUser(user.id)
      users.value = users.value.filter((u) => u.id !== user.id)
      toast.add({ severity: 'success', summary: 'Удалён', detail: user.name, life: 3000 })
    } catch (e: unknown) {
      toast.add({
        severity: 'error',
        summary: 'Ошибка',
        detail: e instanceof Error ? e.message : 'Ошибка',
        life: 4000,
      })
    }
  }

  async function silentRefresh() {
    try {
      const [u, n] = await Promise.all([usersApi.getUsers(), nodesApi.getNodes()])
      if (u) users.value = u
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
