<template>
  <article class="settings-card telegram-proxy-status-card">
    <div class="section-header">
      <p>{{ t('telegramProxy.statusTitle') }}</p>
      <h3>{{ t('telegramProxy.publicLinkTitle') }}</h3>
    </div>

    <div class="status-grid">
      <div class="stat-pill">
        <span>{{ t('telegramProxy.primaryNodeLabel') }}</span>
        <strong>{{ primaryNodeName }}</strong>
      </div>
      <div class="stat-pill">
        <span>{{ t('telegramProxy.publicLinkLabel') }}</span>
        <strong>{{ publicLinkStateLabel }}</strong>
      </div>
      <div class="stat-pill">
        <span>{{ t('telegramProxy.lastRotationLabel') }}</span>
        <strong>{{ lastRotationLabel }}</strong>
      </div>
    </div>

    <div class="public-link-row">
      <div>
        <p class="section-note">{{ t('telegramProxy.primaryPublicLink') }}</p>
        <code
          style="
            display: block;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          "
          >{{ publicLink || t('telegramProxy.noPublicLink') }}</code
        >
      </div>
      <Button
        :label="t('telegramProxy.copyPublicLink')"
        severity="secondary"
        outlined
        :disabled="!publicLink"
        @click="emit('copyLink')"
      />
    </div>

    <Message v-if="primaryStateError" severity="error" :closable="false">{{
      primaryStateError
    }}</Message>

    <div class="status-grid status-metrics">
      <div>
        <span>{{ t('telegramProxy.lastCheckedLabel') }}</span>
        <strong>{{ lastCheckedLabel }}</strong>
      </div>
      <div>
        <span>{{ t('telegramProxy.lastAppliedLabel') }}</span>
        <strong>{{ lastAppliedLabel }}</strong>
      </div>
      <div>
        <span>{{ t('telegramProxy.lastErrorLabel') }}</span>
        <strong>{{ lastErrorLabel }}</strong>
      </div>
    </div>

    <div class="section-header">
      <p>{{ t('telegramProxy.nodeTableTitle') }}</p>
      <h3>{{ t('telegramProxy.nodeTableTitle') }}</h3>
    </div>

    <div v-if="!nodeRows.length" class="muted-card">{{ t('telegramProxy.nodeTableEmpty') }}</div>
    <div v-else class="table-wrap">
      <table class="status-table">
        <thead>
          <tr>
            <th>{{ t('telegramProxy.tableNode') }}</th>
            <th>{{ t('telegramProxy.tableRole') }}</th>
            <th>{{ t('telegramProxy.tableStatus') }}</th>
            <th>{{ t('telegramProxy.tableHost') }}</th>
            <th>{{ t('telegramProxy.tablePort') }}</th>
            <th>{{ t('telegramProxy.tableUpdated') }}</th>
            <th>{{ t('telegramProxy.tableError') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in nodeRows" :key="row.id">
            <td :data-label="t('telegramProxy.tableNode')">{{ row.name }}</td>
            <td :data-label="t('telegramProxy.tableRole')">{{ row.roleLabel }}</td>
            <td :data-label="t('telegramProxy.tableStatus')">
              <Tag :severity="row.statusSeverity">{{ row.statusLabel }}</Tag>
            </td>
            <td :data-label="t('telegramProxy.tableHost')">{{ row.publicHost }}</td>
            <td :data-label="t('telegramProxy.tablePort')">{{ row.publicPort }}</td>
            <td :data-label="t('telegramProxy.tableUpdated')">{{ row.updatedAt }}</td>
            <td :data-label="t('telegramProxy.tableError')">{{ row.error }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import type { Node, TelegramProxyNodeState, TelegramProxyStatus } from '../../api/types'
import { formatDateTime } from '../../utils/format'

type ProxyNodeStatus = 'disabled' | 'not_configured' | 'pending' | 'active' | 'failed'

interface ProxyNodeRow {
  id: string
  name: string
  roleLabel: string
  statusLabel: string
  statusSeverity: string
  publicHost: string
  publicPort: string
  updatedAt: string
  error: string
}

const props = defineProps<{
  status: TelegramProxyStatus | null
  nodes: Node[]
}>()

const emit = defineEmits<{
  copyLink: []
}>()

const { t } = useI18n()

const primaryState = computed<TelegramProxyNodeState | null>(
  () => props.status?.primary_node_state ?? null,
)
const primaryNodeName = computed(() => {
  const primaryId = props.status?.settings.primary_node_id
  const node = props.nodes.find((item) => item.id === primaryId) ?? null
  return node?.name ?? t('telegramProxy.primaryNodeMissing')
})
const publicLink = computed(
  () => props.status?.links?.t_me_url ?? props.status?.links?.tg_url ?? '',
)
const publicLinkStateLabel = computed(() =>
  publicLink.value ? t('telegramProxy.linkAvailable') : t('telegramProxy.linkMissing'),
)
const lastRotationLabel = computed(() => {
  const value = props.status?.settings.last_rotation_at
  return value ? formatDateTime(value) : t('common.notSet')
})
const lastCheckedLabel = computed(() => {
  const value = primaryState.value?.last_checked_at
  return value ? formatDateTime(value) : t('common.notSet')
})
const lastAppliedLabel = computed(() => {
  const value = primaryState.value?.last_applied_at
  return value ? formatDateTime(value) : t('common.notSet')
})
const lastErrorLabel = computed(() => primaryState.value?.last_error ?? t('common.notSet'))
const primaryStateError = computed(() => primaryState.value?.last_error ?? null)
const nodeRows = computed<ProxyNodeRow[]>(() =>
  props.nodes.map((node) => {
    const isPrimary = node.id === props.status?.settings.primary_node_id
    const rowStatus = resolveRowStatus(
      props.status?.settings.enabled ?? false,
      isPrimary,
      primaryState.value,
    )
    return {
      id: node.id,
      name: node.name,
      roleLabel: isPrimary ? t('telegramProxy.primaryRole') : t('telegramProxy.secondaryRole'),
      statusLabel: proxyLabel(rowStatus),
      statusSeverity: proxySeverity(rowStatus),
      publicHost: isPrimary
        ? primaryState.value?.public_host ?? t('common.notSet')
        : t('common.notSet'),
      publicPort:
        isPrimary && primaryState.value?.public_port
          ? String(primaryState.value.public_port)
          : t('common.notSet'),
      updatedAt: isPrimary ? formatNodeStateTime(primaryState.value) : t('common.notSet'),
      error: isPrimary ? primaryState.value?.last_error ?? t('common.notSet') : t('common.notSet'),
    }
  }),
)

function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${String(value)}`)
}

function formatNodeStateTime(state: TelegramProxyNodeState | null): string {
  if (!state) return t('common.notSet')
  return state.last_checked_at ? formatDateTime(state.last_checked_at) : t('common.notSet')
}

function resolveStateStatus(state: TelegramProxyNodeState | null): ProxyNodeStatus {
  if (!state || state.status === 'unknown') return 'pending'
  switch (state.status) {
    case 'active':
    case 'ready':
      return 'active'
    case 'disabled':
      return 'disabled'
    case 'failed':
      return 'failed'
    case 'pending':
      return 'pending'
    default:
      return 'pending'
  }
}

function resolveRowStatus(
  enabled: boolean,
  primary: boolean,
  state: TelegramProxyNodeState | null,
): ProxyNodeStatus {
  if (!enabled) return 'disabled'
  if (!primary) return 'not_configured'
  return resolveStateStatus(state)
}

function proxyLabel(statusValue: ProxyNodeStatus): string {
  switch (statusValue) {
    case 'disabled':
      return t('status.disabled')
    case 'not_configured':
      return t('telegramProxy.notConfigured')
    case 'pending':
      return t('status.pending')
    case 'active':
      return t('status.active')
    case 'failed':
      return t('status.failed')
    default:
      return assertNever(statusValue)
  }
}

function proxySeverity(statusValue: ProxyNodeStatus): string {
  switch (statusValue) {
    case 'active':
      return 'success'
    case 'pending':
      return 'warn'
    case 'failed':
      return 'danger'
    case 'disabled':
      return 'secondary'
    case 'not_configured':
      return 'info'
    default:
      return assertNever(statusValue)
  }
}
</script>

<style scoped>
.telegram-proxy-status-card {
  display: grid;
  gap: var(--app-space-4);
  min-width: 0;
}

.status-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.public-link-row {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  gap: var(--app-space-3);
  flex-wrap: wrap;
}

.public-link-row > div {
  min-width: 0;
  flex: 1 1 0;
  width: 0;
}

.public-link-code {
  display: block;
  max-width: 100%;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.table-wrap {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow-x: auto;
}

.status-table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
}

.status-table th,
.status-table td {
  padding: 0.7rem 0.5rem;
  border-bottom: 1px solid var(--app-border);
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}

.status-table th {
  color: var(--app-text-soft);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

@media (max-width: 1100px) {
  .status-metrics,
  .public-link-row {
    grid-template-columns: 1fr;
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 640px) {
  .public-link-row {
    flex-direction: column;
    align-items: stretch;
  }

  .public-link-row {
    align-items: stretch;
  }

  .public-link-row > div {
    width: 100%;
  }

  .public-link-code {
    white-space: normal;
  }

  .status-table,
  .status-table thead,
  .status-table tbody,
  .status-table tr,
  .status-table th,
  .status-table td {
    display: block;
    width: 100%;
  }

  .status-table thead {
    display: none;
  }

  .status-table tr {
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--app-border);
  }

  .status-table td {
    border-bottom: none;
    padding: 0.25rem 0;
    white-space: normal;
  }

  .status-table td::before {
    content: attr(data-label) ': ';
    color: var(--app-text-soft);
    font-weight: 700;
  }
}
</style>
