<template>
  <aside v-if="user" class="user-detail-drawer" data-testid="user-detail">
    <div class="drawer-head">
      <div>
        <span class="page-kicker"><i class="pi pi-id-card" /> {{ $t('userDetail.kicker') }}</span>
        <h3>{{ user.name }}</h3>
        <p>
          {{ user.remnawave ? $t('userDetail.identityRemnawave') : $t('userDetail.identityLocal') }}
        </p>
      </div>
      <Button
        icon="pi pi-times"
        text
        rounded
        severity="secondary"
        :aria-label="$t('userDetail.close')"
        @click="$emit('close')"
      />
    </div>

    <div class="drawer-status-row">
      <Tag
        :severity="user.is_blocked ? 'danger' : 'success'"
        :value="user.is_blocked ? $t('userTable.statusBlocked') : $t('userTable.statusActive')"
      />
      <Tag
        :severity="user.online ? 'success' : 'secondary'"
        :value="user.online ? $t('userTable.statusOnline') : $t('userTable.statusOffline')"
      />
      <Tag v-if="user.remnawave" severity="info" :value="$t('userTable.readonlyExternal')" />
      <Tag
        v-if="user.remnawave"
        :severity="syncSeverity(user.remnawave.sync_status, user.remnawave.sync_error)"
        :value="user.remnawave.sync_error ? $t('userTable.syncError') : user.remnawave.sync_status"
      />
    </div>

    <section class="detail-section detail-section--accent">
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.nextActions') }}</h4>
        <p>{{ $t('userDetail.nextActionsHint') }}</p>
      </div>
      <div class="drawer-action-grid">
        <Button
          :label="$t('userDetail.copyLink')"
          icon="pi pi-link"
          severity="secondary"
          outlined
          @click="$emit('copyUserLink', user)"
        />
        <Button
          :label="$t('userDetail.traffic')"
          icon="pi pi-chart-bar"
          severity="secondary"
          outlined
          @click="$emit('showTraffic', user)"
        />
        <Button
          v-if="!user.remnawave"
          :label="$t('userDetail.rotateLink')"
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          @click="$emit('regenerateLink', user)"
        />
        <Button
          v-if="user.remnawave"
          :label="$t('userDetail.resyncUser')"
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          :loading="syncingUser"
          @click="$emit('syncRemnawaveUser', user)"
        />
        <template v-else>
          <Button
            v-if="user.is_blocked"
            :label="$t('userDetail.unblock')"
            icon="pi pi-lock-open"
            severity="success"
            outlined
            @click="$emit('unblock', user)"
          />
          <Button
            v-else
            :label="$t('userDetail.block')"
            icon="pi pi-ban"
            severity="warn"
            outlined
            @click="$emit('block', user)"
          />
        </template>
      </div>
    </section>

    <section v-if="!user.remnawave" class="detail-section detail-section--accent">
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.lifecycle') }}</h4>
        <p>{{ $t('userDetail.lifecycleHint') }}</p>
      </div>
      <div class="lifecycle-form-grid">
        <label>
          <span>{{ $t('userDetail.labelExpires') }}</span>
          <input
            :value="dateInput(user)"
            type="datetime-local"
            @change="onExpireChange(user, $event)"
          />
        </label>
        <label>
          <span>{{ $t('userDetail.labelTrafficLimit') }}</span>
          <input
            :value="limitGb(user)"
            type="number"
            min="0"
            step="1"
            @change="onLimitChange(user, $event)"
          />
        </label>
        <label>
          <span>{{ $t('userDetail.labelResetPolicy') }}</span>
          <select
            :value="user.lifecycle?.traffic_reset_policy ?? user.traffic_reset_policy"
            @change="onPolicyChange(user, $event)"
          >
            <option value="manual">{{ $t('userDetail.resetManual') }}</option>
            <option value="no_reset">{{ $t('userDetail.resetDisabled') }}</option>
          </select>
        </label>
      </div>
      <div class="drawer-action-grid">
        <Button
          :label="$t('userDetail.resetTraffic')"
          icon="pi pi-history"
          severity="secondary"
          outlined
          :disabled="
            (user.lifecycle?.traffic_reset_policy ?? user.traffic_reset_policy) !== 'manual'
          "
          @click="$emit('resetTraffic', user)"
        />
      </div>
    </section>

    <section class="detail-section">
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.configsAndQr') }}</h4>
        <p>{{ $t('userDetail.configsHint') }}</p>
      </div>
      <div v-if="readyNodes.length" class="config-node-list">
        <article v-for="node in readyNodes" :key="node.id" class="config-node-card">
          <div>
            <strong>{{ node.name }}</strong>
            <code>{{ node.server_endpoint }}</code>
          </div>
          <div class="config-node-actions">
            <Button
              icon="pi pi-download"
              :label="$t('userDetail.config')"
              size="small"
              text
              severity="secondary"
              @click="$emit('downloadConfig', user, node)"
            />
            <Button
              icon="pi pi-qrcode"
              :label="$t('userDetail.qr')"
              size="small"
              text
              severity="secondary"
              @click="$emit('showQr', user, node)"
            />
          </div>
        </article>
        <Button
          v-if="readyNodes.length > 1"
          :label="$t('userDetail.downloadZip')"
          icon="pi pi-file-export"
          severity="secondary"
          outlined
          @click="$emit('downloadConfigZip', user)"
        />
      </div>
      <div v-else class="drawer-empty">{{ $t('userDetail.noReadyNodes') }}</div>
    </section>

    <section class="detail-section">
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.overview') }}</h4>
      </div>
      <div class="detail-grid">
        <div>
          <span>{{ $t('userDetail.labelId') }}</span
          ><code>{{ user.id }}</code>
        </div>
        <div>
          <span>{{ $t('userDetail.labelVpnIp') }}</span
          ><b>{{ user.vpn_ip || '—' }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelPublicKey') }}</span
          ><code>{{ user.public_key || '—' }}</code>
        </div>
        <div>
          <span>{{ $t('userDetail.labelCreated') }}</span
          ><b>{{ formatDateTimeOrDash(user.created_at) }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelTraffic') }}</span
          ><b>{{ trafficValue(user) }}</b>
        </div>
      </div>
    </section>

    <section class="detail-section">
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.nodes') }}</h4>
      </div>
      <div v-if="user.peers.length" class="peer-detail-list">
        <article v-for="peer in sortedPeers" :key="peer.node_id" class="peer-detail-card">
          <div class="peer-head">
            <strong>{{ peer.node_name }}</strong>
            <Tag
              :severity="peerSeverity(peer.status, user.is_blocked)"
              :value="peerLabel(peer.status, user.is_blocked)"
            />
          </div>
          <div class="detail-grid detail-grid--single">
            <div>
              <span>{{ $t('userDetail.labelOnline') }}</span
              ><b>{{
                peer.online ? $t('userTable.statusOnline') : $t('userTable.statusOffline')
              }}</b>
            </div>
            <div>
              <span>{{ $t('userDetail.labelLastHandshake') }}</span
              ><b>{{ fmtHandshake(peer.last_handshake) }}</b>
            </div>
            <div>
              <span>{{ $t('userDetail.labelEndpoint') }}</span
              ><code>{{ peer.endpoint || '—' }}</code>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="drawer-empty">{{ $t('userDetail.noPeers') }}</div>
    </section>

    <section
      v-if="user.remnawave"
      class="detail-section detail-section--rw"
      data-testid="remnawave-metadata"
    >
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.remnawaveData') }}</h4>
        <p>{{ $t('userDetail.remnawaveDataHint') }}</p>
      </div>
      <div class="detail-grid">
        <div>
          <span>{{ $t('userDetail.labelUuid') }}</span
          ><code>{{ user.remnawave.uuid }}</code>
        </div>
        <div>
          <span>{{ $t('userDetail.labelUsername') }}</span
          ><b>{{ user.remnawave.username }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelEmail') }}</span
          ><b>{{ user.remnawave.email || '—' }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelStatus') }}</span
          ><b>{{ user.remnawave.status }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelExpires') }}</span
          ><b>{{ fmtDate(user.remnawave.expire_at) }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelTrafficLimit') }}</span
          ><b>{{ trafficLimit(user.remnawave.traffic_limit_bytes) }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelCombinedUsed') }}</span
          ><b>{{ fmtBytes(user.remnawave.combined_traffic_used_bytes) }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelBlockedReason') }}</span
          ><b>{{ user.remnawave.blocked_reason || '—' }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelLastSync') }}</span
          ><b>{{ formatDateTimeOrDash(user.remnawave.last_synced_at) }}</b>
        </div>
        <div>
          <span>{{ $t('userDetail.labelSyncReason') }}</span
          ><b>{{ user.remnawave.sync_reason || '—' }}</b>
        </div>
        <div class="detail-wide">
          <span>{{ $t('userDetail.labelSyncError') }}</span
          ><code>{{ user.remnawave.sync_error || '—' }}</code>
        </div>
      </div>
    </section>

    <section v-if="!user.remnawave" class="detail-section detail-section--danger">
      <div class="section-header compact-section-header">
        <h4>{{ $t('userDetail.dangerZone') }}</h4>
        <p>{{ $t('userDetail.dangerZoneHint') }}</p>
      </div>
      <Button
        :label="$t('userDetail.deleteUser')"
        icon="pi pi-trash"
        severity="danger"
        outlined
        @click="$emit('confirmDelete', $event, user)"
      />
    </section>
  </aside>

  <aside v-else class="user-detail-placeholder" data-testid="user-detail-placeholder">
    <i class="pi pi-arrow-left" />
    <strong>{{ $t('userDetail.placeholderTitle') }}</strong>
    <span>{{ $t('userDetail.placeholderText') }}</span>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { fmtBytes, fmtDate, fmtHandshake, formatDateTime } from '../../utils/format'
import { peerLabel, peerSeverity } from '../../utils/status'
import type { Node, User } from '../../api'

const { t } = useI18n()

const props = defineProps<{
  user: User | null
  readyNodes: Node[]
  syncingUser: boolean
}>()

const emit = defineEmits<{
  close: []
  block: [user: User]
  unblock: [user: User]
  confirmDelete: [event: Event, user: User]
  showTraffic: [user: User]
  copyUserLink: [user: User]
  regenerateLink: [user: User]
  updateLifecycle: [
    user: User,
    payload: {
      expire_at: string | null
      traffic_limit_bytes: number
      traffic_reset_policy: 'manual' | 'no_reset'
    },
  ]
  resetTraffic: [user: User]
  downloadConfig: [user: User, node: Node]
  downloadConfigZip: [user: User]
  showQr: [user: User, node: Node]
  syncRemnawaveUser: [user: User]
}>()

function formatDateTimeOrDash(iso?: string | null): string {
  return iso ? formatDateTime(iso) : '—'
}

function trafficValue(user: User): string {
  if (user.remnawave) return fmtBytes(user.remnawave.combined_traffic_used_bytes)
  return user.local_traffic ? fmtBytes(user.local_traffic.total_bytes) : '—'
}

function trafficLimit(value: number): string {
  return value > 0 ? fmtBytes(value) : t('userDetail.noLimit')
}

function dateInput(user: User): string {
  const value = user.lifecycle?.expire_at ?? user.expire_at
  return value ? value.slice(0, 16) : ''
}

function limitGb(user: User): number {
  const value = user.lifecycle?.traffic_limit_bytes ?? user.traffic_limit_bytes
  return Math.round(value / 1024 ** 3)
}

function onExpireChange(user: User, event: Event) {
  const target = event.target as { value?: unknown } | null
  if (!target || target.value === undefined) return
  emitLifecycle(user, {
    expire_at: String(target.value || '') || null,
    traffic_limit_bytes: user.lifecycle?.traffic_limit_bytes ?? user.traffic_limit_bytes,
    traffic_reset_policy: user.lifecycle?.traffic_reset_policy ?? user.traffic_reset_policy,
  })
}

function onLimitChange(user: User, event: Event) {
  const target = event.target as { value?: unknown } | null
  if (!target || target.value === undefined) return
  emitLifecycle(user, {
    expire_at: user.lifecycle?.expire_at ?? user.expire_at,
    traffic_limit_bytes: Number(target.value || 0) * 1024 ** 3,
    traffic_reset_policy: user.lifecycle?.traffic_reset_policy ?? user.traffic_reset_policy,
  })
}

function onPolicyChange(user: User, event: Event) {
  const target = event.target as { value?: unknown } | null
  if (!target || target.value === undefined) return
  emitLifecycle(user, {
    expire_at: user.lifecycle?.expire_at ?? user.expire_at,
    traffic_limit_bytes: user.lifecycle?.traffic_limit_bytes ?? user.traffic_limit_bytes,
    traffic_reset_policy: String(target.value) === 'no_reset' ? 'no_reset' : 'manual',
  })
}

function emitLifecycle(
  user: User,
  payload: {
    expire_at: string | null
    traffic_limit_bytes: number
    traffic_reset_policy: 'manual' | 'no_reset'
  },
) {
  emit('updateLifecycle', user, payload)
}

function syncSeverity(status: string, error: string | null): string {
  if (error || status === 'failed' || status === 'error') return 'danger'
  if (status === 'synced') return 'success'
  return 'warn'
}

function compareText(left: string | null | undefined, right: string | null | undefined): number {
  return (left ?? '').localeCompare(right ?? '', 'ru', { sensitivity: 'base' })
}

const sortedPeers = computed(() => {
  if (!props.user) return []

  return [...props.user.peers].sort((left, right) => {
    const nameDiff = compareText(left.node_name, right.node_name)
    if (nameDiff !== 0) return nameDiff

    return compareText(left.node_id, right.node_id)
  })
})
</script>

<style scoped>
.user-detail-drawer,
.user-detail-placeholder {
  min-width: 0;
  align-self: start;
  max-height: calc(100vh - 3rem);
  overflow: auto;
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-lg);
  background: linear-gradient(
    180deg,
    var(--app-shell-solid),
    color-mix(in srgb, var(--app-shell-solid) 90%, var(--app-bg-accent))
  );
  box-shadow: var(--app-shadow);
}

.user-detail-placeholder {
  display: grid;
  gap: 0.5rem;
  place-items: center;
  min-height: 18rem;
  padding: var(--app-space-5);
  color: var(--app-text-muted);
  text-align: center;
}

.drawer-head {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: var(--app-space-5);
  border-bottom: 1px solid var(--app-border);
}

.drawer-head h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 1.35rem;
  font-weight: 950;
  overflow-wrap: anywhere;
}

.drawer-head p {
  margin: 0.3rem 0 0;
  color: var(--app-text-muted);
}

.drawer-status-row,
.drawer-action-grid,
.config-node-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.drawer-status-row {
  padding: 0 var(--app-space-5) var(--app-space-4);
}

.detail-section {
  display: grid;
  gap: 0.85rem;
  margin: 0 var(--app-space-5) var(--app-space-4);
  padding: var(--app-space-4);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: color-mix(in srgb, var(--app-surface-raised) 76%, transparent);
}

.detail-section--accent {
  border-color: color-mix(in srgb, var(--app-accent) 40%, var(--app-border));
}

.detail-section--rw {
  border-color: color-mix(in srgb, var(--app-cyan) 42%, var(--app-border));
}

.detail-section--danger {
  border-color: color-mix(in srgb, var(--app-red) 36%, var(--app-border));
}

.lifecycle-form-grid {
  display: grid;
  gap: 0.75rem;
}

.lifecycle-form-grid label {
  display: grid;
  gap: 0.35rem;
}

.lifecycle-form-grid input,
.lifecycle-form-grid select {
  width: 100%;
  min-height: 2.5rem;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--app-border-strong);
  border-radius: 0.8rem;
  background: var(--app-shell-solid);
  color: var(--app-text);
}

.compact-section-header {
  margin-bottom: 0;
}

.compact-section-header h4 {
  margin: 0;
  color: var(--app-text);
  font-size: 0.86rem;
  font-weight: 950;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.config-node-list,
.peer-detail-list {
  display: grid;
  gap: 0.6rem;
}

.config-node-card,
.peer-detail-card {
  display: grid;
  gap: 0.6rem;
  padding: 0.75rem;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: color-mix(in srgb, var(--app-shell-solid) 80%, transparent);
}

.config-node-card {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.config-node-card strong,
.peer-detail-card strong {
  display: block;
  margin-bottom: 0.25rem;
  color: var(--app-text);
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.detail-grid--single {
  grid-template-columns: 1fr;
}

.detail-grid > div {
  display: grid;
  gap: 0.25rem;
  min-width: 0;
}

.detail-grid span {
  color: var(--app-text-soft);
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-grid b {
  color: var(--app-text);
  overflow-wrap: anywhere;
}

.detail-grid code {
  overflow-wrap: anywhere;
  white-space: normal;
}

.detail-wide {
  grid-column: 1 / -1;
}

.peer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.drawer-empty {
  color: var(--app-text-muted);
  padding: 0.9rem;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-sm);
}

@media (max-width: 980px) {
  .user-detail-drawer,
  .user-detail-placeholder {
    max-height: none;
  }
}

@media (max-width: 640px) {
  .detail-grid,
  .config-node-card {
    grid-template-columns: 1fr;
  }
}
</style>
