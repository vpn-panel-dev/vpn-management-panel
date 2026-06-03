<template>
  <div>
    <div class="page-header users-page-header">
      <div>
        <span class="page-kicker"><i class="pi pi-users" /> Access workspace</span>
        <h2>Пользователи</h2>
        <p class="page-description">
          Компактный roster для быстрого поиска, фильтрации и выбора next action. Remnawave metadata
          вынесена в detail, чтобы список не превращался в диагностический лог.
        </p>
        <div class="page-stats">
          <span class="stat-pill"
            ><span>Всего</span><strong>{{ facets.total }}</strong></span
          >
          <span class="stat-pill"
            ><span>Online</span><strong>{{ facets.online }}</strong></span
          >
          <span class="stat-pill"
            ><span>Blocked</span><strong>{{ facets.blocked }}</strong></span
          >
          <span class="stat-pill"
            ><span>Remnawave</span><strong>{{ facets.remnawave }}</strong></span
          >
          <span class="stat-pill stat-pill--danger"
            ><span>Sync issues</span><strong>{{ facets.syncIssues }}</strong></span
          >
        </div>
      </div>
      <div class="user-create-card page-actions">
        <InputText
          v-model="newName"
          placeholder="Имя локального пользователя"
          size="small"
          @keyup.enter="addUser"
        />
        <Button
          label="Добавить"
          icon="pi pi-plus"
          size="small"
          :loading="addingUser"
          @click="addUser"
        />
      </div>
    </div>

    <section class="users-controls" data-testid="users-controls">
      <div class="search-box">
        <i class="pi pi-search" />
        <InputText
          v-model="query.search"
          placeholder="Search name, IP, UUID, email, node, sync error"
          size="small"
        />
      </div>
      <div class="filter-rail" aria-label="Фильтры пользователей">
        <button
          v-for="filter in statusFilters"
          :key="filter.key"
          type="button"
          :class="['filter-chip', { 'filter-chip--active': query.status === filter.key }]"
          @click="setStatus(filter.key)"
        >
          <span>{{ filter.label }}</span>
          <strong>{{ filter.count }}</strong>
        </button>
      </div>
      <div class="control-row">
        <label>
          Source
          <select v-model="query.source">
            <option value="all">All</option>
            <option value="local">Local</option>
            <option value="remnawave">Remnawave</option>
          </select>
        </label>
        <label>
          Sort
          <select v-model="query.sort">
            <option value="name">Name</option>
            <option value="status">Status</option>
            <option value="source">Source</option>
            <option value="traffic">Traffic</option>
            <option value="expiration">Expiration</option>
            <option value="sync">Sync issues</option>
          </select>
        </label>
        <label>
          Page size
          <select v-model.number="query.pageSize">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </label>
      </div>
    </section>

    <Message v-if="loadError" severity="error" :closable="false" class="users-error">
      {{ loadError }}
    </Message>

    <div class="users-shell">
      <div class="users-list-column">
        <div class="list-summary-row">
          <span>Показано {{ visibleUsers.length }} из {{ listResponse.total }}</span>
          <span v-if="query.search">Search: “{{ query.search }}”</span>
        </div>

        <UserTable
          :users="visibleUsers"
          :loading="loading"
          :selected-id="selectedUser?.id ?? null"
          :empty-title="emptyTitle"
          :empty-text="emptyText"
          @select="selectUser"
          @copy-user-link="copyUserLink"
        />

        <div
          v-if="listResponse.total > query.pageSize"
          class="pagination-bar"
          data-testid="users-pagination"
        >
          <Button
            label="Назад"
            icon="pi pi-angle-left"
            severity="secondary"
            outlined
            size="small"
            :disabled="query.page === 1"
            @click="query.page -= 1"
          />
          <span>Страница {{ query.page }} / {{ pageCount }}</span>
          <Button
            label="Вперёд"
            icon="pi pi-angle-right"
            icon-pos="right"
            severity="secondary"
            outlined
            size="small"
            :disabled="query.page >= pageCount"
            @click="query.page += 1"
          />
        </div>
      </div>

      <UserDetailDrawer
        :user="selectedUser"
        :ready-nodes="readyNodes"
        :syncing-user="syncingUser"
        @close="clearSelectedUser"
        @block="block"
        @unblock="unblock"
        @confirm-delete="confirmDelete"
        @show-traffic="showTraffic"
        @copy-user-link="copyUserLink"
        @download-config="downloadConfig"
        @download-config-zip="downloadConfigZip"
        @show-qr="showQr"
        @sync-remnawave-user="syncRemnawaveUser"
      />
    </div>

    <UserQrDialog
      :visible="qrDialog.visible"
      :title="qrDialog.title"
      :src-wg="qrDialog.srcWg"
      :src-amnezia="qrDialog.srcAmnezia"
      :current-tab="qrDialog.tab"
      @update:visible="qrDialog.visible = $event"
      @update:tab="qrDialog.tab = $event"
    />

    <ConfirmPopup />

    <UserTrafficDialog
      :visible="trafficDialog.visible"
      :title="trafficDialog.title"
      :loading="trafficDialog.loading"
      :data="trafficDialog.data"
      :max-val="trafficDialog.maxVal"
      :user="trafficDialog.user"
      :local-totals="trafficDialog.localTotals"
      :local-daily="trafficDialog.localDaily"
      :local-nodes="trafficDialog.localNodes"
      :local-nodes-daily="trafficDialog.localNodesDaily"
      @update:visible="trafficDialog.visible = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Message from 'primevue/message'
import ConfirmPopup from 'primevue/confirmpopup'
import UserTable from '../components/users/UserTable.vue'
import UserDetailDrawer from '../components/users/UserDetailDrawer.vue'
import UserQrDialog from '../components/users/UserQrDialog.vue'
import UserTrafficDialog from '../components/users/UserTrafficDialog.vue'
import { remnawaveApi } from '../api/remnawave'
import { usersApi } from '../api/users'
import { useUsers } from '../composables/useUsers'
import { useDownloads } from '../composables/useDownloads'
import type { User, UserListQuery, UserStatusFilter } from '../api'

const route = useRoute()
const router = useRouter()
const toast = useToast()

const {
  users,
  loading,
  loadError,
  newName,
  addingUser,
  readyNodes,
  addUser,
  block,
  unblock,
  confirmDelete,
} = useUsers()

const query = reactive<UserListQuery>({
  search: '',
  source: 'all',
  status: 'all',
  sort: 'name',
  page: 1,
  pageSize: 20,
})

const syncingUser = ref(false)

const listResponse = computed(() => usersApi.queryLocalUsers(users.value, query))
const visibleUsers = computed(() => listResponse.value.items)
const facets = computed(() => listResponse.value.facets)
const pageCount = computed(() => Math.max(1, Math.ceil(listResponse.value.total / query.pageSize)))
const selectedUser = computed(() => users.value.find((user) => user.id === route.params.id) ?? null)

const statusFilters = computed(() => [
  { key: 'all' as const, label: 'All', count: facets.value.total },
  { key: 'active' as const, label: 'Active', count: facets.value.total - facets.value.blocked },
  { key: 'blocked' as const, label: 'Blocked', count: facets.value.blocked },
  { key: 'expiring' as const, label: 'Expiring soon', count: facets.value.expiring },
  { key: 'sync_issues' as const, label: 'Sync issues', count: facets.value.syncIssues },
])

const emptyTitle = computed(() =>
  users.value.length ? 'Ничего не найдено' : 'Пользователей пока нет',
)
const emptyText = computed(() =>
  users.value.length
    ? 'Сбросьте поиск или фильтры, чтобы увидеть больше пользователей.'
    : 'Создайте локального пользователя или включите синхронизацию Remnawave.',
)

const {
  qrDialog,
  trafficDialog,
  showQr,
  downloadConfig,
  downloadConfigZip,
  copyUserLink,
  showTraffic,
} = useDownloads()

watch(
  () => [query.search, query.source, query.status, query.sort, query.pageSize],
  () => {
    query.page = 1
  },
)

watch(
  () => users.value,
  () => {
    if (selectedUser.value || !route.params.id) return
    void router.replace('/users')
  },
)

function setStatus(status: UserStatusFilter) {
  query.status = status
}

function selectUser(user: User) {
  void router.push(`/users/${user.id}${window.location.search}`)
}

function clearSelectedUser() {
  void router.push(`/users${window.location.search}`)
}

async function syncRemnawaveUser(user: User) {
  if (!user.remnawave) return
  syncingUser.value = true
  try {
    const result = await remnawaveApi.syncRemnawaveUser(user.remnawave.uuid)
    toast.add({
      severity: 'success',
      summary: 'Sync queued',
      detail: result?.operation_id ?? user.remnawave.uuid,
      life: 3000,
    })
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка sync',
      detail: e instanceof Error ? e.message : 'Не удалось запустить sync',
      life: 4000,
    })
  } finally {
    syncingUser.value = false
  }
}
</script>

<style scoped>
.users-page-header {
  align-items: stretch;
}

.stat-pill--danger strong {
  color: var(--app-red);
}

.user-create-card {
  align-self: end;
}

.users-controls {
  display: grid;
  gap: var(--app-space-3);
  margin-bottom: var(--app-space-4);
  padding: var(--app-space-4);
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-lg);
  background: color-mix(in srgb, var(--app-shell-solid) 88%, transparent);
  box-shadow: var(--app-shadow);
}

.search-box {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
}

.search-box i {
  color: var(--app-text-soft);
}

.filter-rail,
.control-row,
.pagination-bar,
.list-summary-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.55rem;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--app-border);
  border-radius: 999px;
  background: color-mix(in srgb, var(--app-surface-raised) 72%, transparent);
  color: var(--app-text-muted);
  cursor: pointer;
  font-weight: 850;
}

.filter-chip--active {
  border-color: color-mix(in srgb, var(--app-accent) 52%, var(--app-border));
  background: color-mix(in srgb, var(--app-accent) 16%, var(--app-shell-solid));
  color: var(--app-text);
}

.filter-chip strong {
  color: var(--app-text);
}

.control-row label {
  display: grid;
  gap: 0.25rem;
  color: var(--app-text-soft);
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.control-row select {
  min-width: 9rem;
  padding: 0.45rem 0.65rem;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-shell-solid);
  color: var(--app-text);
}

.users-error {
  margin-bottom: var(--app-space-4);
}

.users-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(22rem, 30rem);
  gap: var(--app-space-4);
  align-items: start;
}

.users-list-column {
  min-width: 0;
}

.list-summary-row {
  justify-content: space-between;
  margin-bottom: 0.65rem;
  color: var(--app-text-muted);
  font-size: 0.82rem;
}

.pagination-bar {
  justify-content: center;
  margin-top: var(--app-space-4);
  color: var(--app-text-muted);
}

@media (max-width: 980px) {
  .users-shell,
  .users-page-header {
    grid-template-columns: 1fr;
  }

  .user-create-card {
    justify-content: stretch;
  }

  .user-create-card :deep(.p-inputtext),
  .user-create-card :deep(.p-button) {
    flex: 1 1 100%;
  }
}

@media (max-width: 640px) {
  .users-controls,
  .page-header {
    padding: var(--app-space-4);
  }

  .filter-rail {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-chip {
    justify-content: space-between;
  }

  .control-row label,
  .control-row select {
    width: 100%;
  }
}
</style>
