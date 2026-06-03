<template>
  <aside v-if="user" class="user-detail-drawer" data-testid="user-detail">
    <div class="drawer-head">
      <div>
        <span class="page-kicker"><i class="pi pi-id-card" /> User detail</span>
        <h3>{{ user.name }}</h3>
        <p>{{ user.remnawave ? 'Readonly Remnawave identity' : 'Local AmneziaWG identity' }}</p>
      </div>
      <Button
        icon="pi pi-times"
        text
        rounded
        severity="secondary"
        aria-label="Закрыть"
        @click="$emit('close')"
      />
    </div>

    <div class="drawer-status-row">
      <Tag
        :severity="user.is_blocked ? 'danger' : 'success'"
        :value="user.is_blocked ? 'blocked' : 'active'"
      />
      <Tag
        :severity="user.online ? 'success' : 'secondary'"
        :value="user.online ? 'online' : 'offline'"
      />
      <Tag v-if="user.remnawave" severity="info" value="readonly external" />
      <Tag
        v-if="user.remnawave"
        :severity="syncSeverity(user.remnawave.sync_status, user.remnawave.sync_error)"
        :value="user.remnawave.sync_error ? 'sync error' : user.remnawave.sync_status"
      />
    </div>

    <section class="detail-section detail-section--accent">
      <div class="section-header compact-section-header">
        <h4>Next actions</h4>
        <p>Самые частые операторские действия без поиска по строке.</p>
      </div>
      <div class="drawer-action-grid">
        <Button
          label="Self-service link"
          icon="pi pi-link"
          severity="secondary"
          outlined
          @click="$emit('copyUserLink', user)"
        />
        <Button
          label="Traffic"
          icon="pi pi-chart-bar"
          severity="secondary"
          outlined
          @click="$emit('showTraffic', user)"
        />
        <Button
          v-if="user.remnawave"
          label="Resync user"
          icon="pi pi-refresh"
          severity="secondary"
          outlined
          :loading="syncingUser"
          @click="$emit('syncRemnawaveUser', user)"
        />
        <template v-else>
          <Button
            v-if="user.is_blocked"
            label="Unblock"
            icon="pi pi-lock-open"
            severity="success"
            outlined
            @click="$emit('unblock', user)"
          />
          <Button
            v-else
            label="Block"
            icon="pi pi-ban"
            severity="warn"
            outlined
            @click="$emit('block', user)"
          />
        </template>
      </div>
    </section>

    <section class="detail-section">
      <div class="section-header compact-section-header">
        <h4>Configs and QR</h4>
        <p>Доступно только для нод с закешированными metadata.</p>
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
              label="Config"
              size="small"
              text
              severity="secondary"
              @click="$emit('downloadConfig', user, node)"
            />
            <Button
              icon="pi pi-qrcode"
              label="QR"
              size="small"
              text
              severity="secondary"
              @click="$emit('showQr', user, node)"
            />
          </div>
        </article>
        <Button
          v-if="readyNodes.length > 1"
          label="Download ZIP"
          icon="pi pi-file-export"
          severity="secondary"
          outlined
          @click="$emit('downloadConfigZip', user)"
        />
      </div>
      <div v-else class="drawer-empty">Нет готовых нод. Сначала выполните node sync.</div>
    </section>

    <section class="detail-section">
      <div class="section-header compact-section-header">
        <h4>Overview</h4>
      </div>
      <div class="detail-grid">
        <div>
          <span>ID</span><code>{{ user.id }}</code>
        </div>
        <div>
          <span>VPN IP</span><b>{{ user.vpn_ip || '—' }}</b>
        </div>
        <div>
          <span>Public key</span><code>{{ user.public_key || '—' }}</code>
        </div>
        <div>
          <span>Created</span><b>{{ formatDateTimeOrDash(user.created_at) }}</b>
        </div>
        <div>
          <span>Traffic</span><b>{{ trafficValue(user) }}</b>
        </div>
      </div>
    </section>

    <section class="detail-section">
      <div class="section-header compact-section-header">
        <h4>Nodes</h4>
      </div>
      <div v-if="user.peers.length" class="peer-detail-list">
        <article v-for="peer in user.peers" :key="peer.node_id" class="peer-detail-card">
          <div class="peer-head">
            <strong>{{ peer.node_name }}</strong>
            <Tag :severity="peerSeverity(peer.status)" :value="peer.status" />
          </div>
          <div class="detail-grid detail-grid--single">
            <div>
              <span>Online</span><b>{{ peer.online ? 'online' : 'offline' }}</b>
            </div>
            <div>
              <span>Last handshake</span><b>{{ fmtHandshake(peer.last_handshake) }}</b>
            </div>
            <div>
              <span>Endpoint</span><code>{{ peer.endpoint || '—' }}</code>
            </div>
          </div>
        </article>
      </div>
      <div v-else class="drawer-empty">Пиры ещё не назначены.</div>
    </section>

    <section
      v-if="user.remnawave"
      class="detail-section detail-section--rw"
      data-testid="remnawave-metadata"
    >
      <div class="section-header compact-section-header">
        <h4>Remnawave metadata</h4>
        <p>Скрыто из списка, доступно в detail для диагностики.</p>
      </div>
      <div class="detail-grid">
        <div>
          <span>UUID</span><code>{{ user.remnawave.uuid }}</code>
        </div>
        <div>
          <span>Username</span><b>{{ user.remnawave.username }}</b>
        </div>
        <div>
          <span>Email</span><b>{{ user.remnawave.email || '—' }}</b>
        </div>
        <div>
          <span>Status</span><b>{{ user.remnawave.status }}</b>
        </div>
        <div>
          <span>Expires</span><b>{{ fmtDate(user.remnawave.expire_at) }}</b>
        </div>
        <div>
          <span>Traffic limit</span><b>{{ trafficLimit(user.remnawave.traffic_limit_bytes) }}</b>
        </div>
        <div>
          <span>Combined used</span
          ><b>{{ fmtBytes(user.remnawave.combined_traffic_used_bytes) }}</b>
        </div>
        <div>
          <span>Blocked reason</span><b>{{ user.remnawave.blocked_reason || '—' }}</b>
        </div>
        <div>
          <span>Last sync</span><b>{{ formatDateTimeOrDash(user.remnawave.last_synced_at) }}</b>
        </div>
        <div>
          <span>Sync reason</span><b>{{ user.remnawave.sync_reason || '—' }}</b>
        </div>
        <div class="detail-wide">
          <span>Sync error</span><code>{{ user.remnawave.sync_error || '—' }}</code>
        </div>
      </div>
    </section>

    <section v-if="!user.remnawave" class="detail-section detail-section--danger">
      <div class="section-header compact-section-header">
        <h4>Danger zone</h4>
        <p>Удаление локального пользователя требует подтверждения.</p>
      </div>
      <Button
        label="Delete local user"
        icon="pi pi-trash"
        severity="danger"
        outlined
        @click="$emit('confirmDelete', $event, user)"
      />
    </section>
  </aside>

  <aside v-else class="user-detail-placeholder" data-testid="user-detail-placeholder">
    <i class="pi pi-arrow-left" />
    <strong>Выберите пользователя</strong>
    <span
      >В списке остаются только поля для сканирования, всё диагностическое открывается здесь.</span
    >
  </aside>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { fmtBytes, fmtDate, fmtHandshake, formatDateTime } from '../../utils/format'
import { peerSeverity } from '../../utils/status'
import type { Node, User } from '../../api'

defineProps<{
  user: User | null
  readyNodes: Node[]
  syncingUser: boolean
}>()

defineEmits<{
  close: []
  block: [user: User]
  unblock: [user: User]
  confirmDelete: [event: Event, user: User]
  showTraffic: [user: User]
  copyUserLink: [user: User]
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
  return value > 0 ? fmtBytes(value) : 'без лимита'
}

function syncSeverity(status: string, error: string | null): string {
  if (error || status === 'failed' || status === 'error') return 'danger'
  if (status === 'synced') return 'success'
  return 'warn'
}
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
