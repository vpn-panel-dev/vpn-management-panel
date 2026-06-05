<template>
  <div>
    <div class="page-header users-page-header">
      <div>
        <span class="page-kicker"><i class="pi pi-users" /> {{ $t('users.kicker') }}</span>
        <h2>{{ $t('users.title') }}</h2>
        <p class="page-description">{{ $t('users.description') }}</p>
        <div class="page-stats">
          <span class="stat-pill"
            ><span>{{ $t('users.total') }}</span
            ><strong>{{ facets.total }}</strong></span
          >
          <span class="stat-pill"
            ><span>{{ $t('users.online') }}</span
            ><strong>{{ facets.online }}</strong></span
          >
          <span class="stat-pill"
            ><span>{{ $t('users.blocked') }}</span
            ><strong>{{ facets.blocked }}</strong></span
          >
          <span class="stat-pill"
            ><span>{{ $t('users.remnawave') }}</span
            ><strong>{{ facets.remnawave }}</strong></span
          >
          <span class="stat-pill stat-pill--danger"
            ><span>{{ $t('users.syncIssues') }}</span
            ><strong>{{ facets.syncIssues }}</strong></span
          >
        </div>
      </div>
      <div class="user-create-card page-actions">
        <InputText
          v-model="newName"
          :placeholder="$t('users.addPlaceholder')"
          size="small"
          @keyup.enter="addUser"
        />
        <Button
          :label="$t('users.addButton')"
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
          :placeholder="$t('users.searchPlaceholder')"
          size="small"
        />
      </div>
      <div class="filter-rail" :aria-label="$t('users.source')">
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
          {{ $t('users.source') }}
          <select v-model="query.source">
            <option value="all">{{ $t('users.sourceAll') }}</option>
            <option value="local">{{ $t('users.sourceLocal') }}</option>
            <option value="remnawave">{{ $t('users.sourceRemnawave') }}</option>
          </select>
        </label>
        <label>
          {{ $t('users.sort') }}
          <select v-model="query.sort">
            <option value="name">{{ $t('users.sortName') }}</option>
            <option value="status">{{ $t('users.sortStatus') }}</option>
            <option value="source">{{ $t('users.sortSource') }}</option>
            <option value="traffic">{{ $t('users.sortTraffic') }}</option>
            <option value="expiration">{{ $t('users.sortExpiration') }}</option>
            <option value="sync">{{ $t('users.sortSync') }}</option>
          </select>
        </label>
        <label>
          {{ $t('users.pageSize') }}
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
          <span>{{
            $t('users.showing', { visible: visibleUsers.length, total: listResponse.total })
          }}</span>
          <span v-if="query.search">{{ $t('users.searchActive', { query: query.search }) }}</span>
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
            :label="$t('users.back')"
            icon="pi pi-angle-left"
            severity="secondary"
            outlined
            size="small"
            :disabled="query.page === 1"
            @click="query.page -= 1"
          />
          <span>{{ $t('users.page', { page: query.page, total: pageCount }) }}</span>
          <Button
            :label="$t('users.forward')"
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
        @regenerate-link="regenerateLink"
        @update-lifecycle="updateLifecycle"
        @reset-traffic="resetTraffic"
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
import { useI18n } from 'vue-i18n'
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
const { t } = useI18n()

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
  { key: 'all' as const, label: t('users.sourceAll'), count: facets.value.total },
  {
    key: 'active' as const,
    label: t('userTable.statusActive'),
    count: facets.value.total - facets.value.blocked,
  },
  { key: 'blocked' as const, label: t('userTable.statusBlocked'), count: facets.value.blocked },
  { key: 'expiring' as const, label: t('status.expired'), count: facets.value.expiring },
  { key: 'sync_issues' as const, label: t('users.syncIssues'), count: facets.value.syncIssues },
])

const emptyTitle = computed(() =>
  users.value.length ? t('users.emptyTitleWithUsers') : t('users.emptyTitleNoUsers'),
)
const emptyText = computed(() =>
  users.value.length ? t('users.emptyTextWithUsers') : t('users.emptyTextNoUsers'),
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
      summary: t('toasts.syncQueued'),
      detail: result?.operation_id ?? user.remnawave.uuid,
      life: 3000,
    })
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: t('toasts.error'),
      detail: e instanceof Error ? e.message : t('toasts.error'),
      life: 4000,
    })
  } finally {
    syncingUser.value = false
  }
}

async function updateLifecycle(
  user: User,
  payload: {
    expire_at: string | null
    traffic_limit_bytes: number
    traffic_reset_policy: 'manual' | 'no_reset'
  },
) {
  try {
    const updated = await usersApi.updateLifecycle(user.id, payload)
    if (updated) Object.assign(user, updated)
    toast.add({
      severity: 'success',
      summary: t('toasts.saved'),
      detail: user.name,
      life: 3000,
    })
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: t('toasts.error'),
      detail: e instanceof Error ? e.message : t('toasts.error'),
      life: 4000,
    })
  }
}

async function resetTraffic(user: User) {
  try {
    const updated = await usersApi.resetTraffic(user.id)
    if (updated) {
      Object.assign(user, updated)
      user.local_traffic = {
        source: 'local_amneziawg',
        user_id: user.id,
        rx_bytes: 0,
        tx_bytes: 0,
        total_bytes: 0,
        updated_at: updated.traffic_reset_at,
      }
    }
    toast.add({
      severity: 'success',
      summary: t('toasts.saved'),
      detail: user.name,
      life: 3000,
    })
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: t('toasts.error'),
      detail: e instanceof Error ? e.message : t('toasts.error'),
      life: 4000,
    })
  }
}

async function regenerateLink(user: User) {
  try {
    const result = await usersApi.regeneratePublicLink(user.id)
    if (result) {
      user.public_token = result.public_token
      copyUserLink(user)
    }
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: t('toasts.error'),
      detail: e instanceof Error ? e.message : t('toasts.error'),
      life: 4000,
    })
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
