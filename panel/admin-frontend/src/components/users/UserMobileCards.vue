<template>
  <div class="mobile-card-list">
    <div v-if="loading" class="mobile-empty">Загрузка пользователей…</div>
    <div v-else-if="!users.length" class="mobile-empty">Нет пользователей.</div>
    <article v-for="user in users" v-else :key="user.id" class="mobile-user-card">
      <div class="mobile-card-head">
        <div>
          <div class="mobile-card-title">{{ user.name }}</div>
          <div class="mobile-card-sub">{{ user.vpn_ip || 'IP ещё не назначен' }}</div>
        </div>
        <div class="mobile-card-tags">
          <Tag
            :severity="user.is_blocked ? 'danger' : 'success'"
            :value="user.is_blocked ? 'заблокирован' : 'активен'"
            style="font-size: 0.75rem"
          />
          <Tag v-if="user.remnawave" severity="info" value="Remnawave" style="font-size: 0.72rem" />
          <Tag
            v-if="user.remnawave"
            :severity="syncSeverity(user.remnawave.sync_status)"
            :value="user.remnawave.sync_status"
            style="font-size: 0.72rem"
          />
          <Tag
            v-if="user.remnawave"
            severity="secondary"
            value="только просмотр"
            style="font-size: 0.72rem"
          />
        </div>
      </div>

      <div v-if="user.remnawave" class="mobile-remnawave-info">
        <div class="mobile-remnawave-head">
          <span class="remnawave-label">Управляется Remnawave</span>
          <Tag
            :severity="remnawaveSeverity(user.remnawave.status)"
            :value="user.remnawave.status"
            style="font-size: 0.72rem"
          />
        </div>
        <div class="mobile-remnawave-grid">
          <div>
            <span>UUID</span>
            <code :title="user.remnawave.uuid">{{ user.remnawave.uuid }}</code>
          </div>
          <div>
            <span>Источник</span>
            <b class="remnawave-source">Remnawave</b>
          </div>
          <div>
            <span>Username</span>
            <b>{{ user.remnawave.username }}</b>
          </div>
          <div>
            <span>Истекает</span>
            <b>{{ fmtDate(user.remnawave.expire_at) }}</b>
          </div>
          <div>
            <span>Лимит трафика</span>
            <b>{{ trafficLimitLabel(user.remnawave.traffic_limit_bytes) }}</b>
          </div>
          <div>
            <span>Последняя синхронизация</span>
            <b>{{ formatDateTimeOrDash(user.remnawave.last_synced_at) }}</b>
          </div>
          <div>
            <span>Причина sync</span>
            <b>{{ user.remnawave.sync_reason || '—' }}</b>
          </div>
          <div class="mobile-remnawave-error">
            <span>Ошибка sync</span>
            <b>{{ user.remnawave.sync_error || '—' }}</b>
          </div>
        </div>
      </div>

      <div class="mobile-fields">
        <div>
          <span>Ноды</span>
          <div v-if="user.peers?.length" class="mobile-peer-list">
            <span v-for="p in user.peers" :key="p.node_id" class="peer-chip">
              <span
                :title="
                  p.last_handshake
                    ? `Последний хендшейк: ${fmtHandshake(p.last_handshake)}`
                    : 'Никогда не подключался'
                "
                :style="{
                  display: 'inline-block',
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: isOnline(p.last_handshake)
                    ? 'var(--p-green-400)'
                    : 'var(--p-surface-400)',
                  flexShrink: 0,
                }"
              />
              <Tag
                :severity="peerSeverity(p.status)"
                :value="p.node_name"
                style="font-size: 0.72rem"
              />
            </span>
          </div>
          <b v-else class="dim">нет</b>
        </div>
        <div>
          <span>Конфиги</span>
          <div v-if="readyNodes.length" class="mobile-config-grid">
            <Button
              v-for="n in readyNodes"
              :key="n.id"
              :label="n.name"
              icon="pi pi-download"
              size="small"
              severity="secondary"
              outlined
              @click="$emit('downloadConfig', user, n)"
            />
            <Button
              v-for="n in readyNodes"
              :key="`qr-${n.id}`"
              :label="`${n.name} QR`"
              icon="pi pi-qrcode"
              size="small"
              severity="secondary"
              outlined
              @click="$emit('showQr', user, n)"
            />
            <Button
              v-if="readyNodes.length > 1"
              label="ZIP"
              icon="pi pi-file-export"
              size="small"
              severity="secondary"
              outlined
              @click="$emit('downloadConfigZip', user)"
            />
          </div>
          <b v-else class="dim">нет нод</b>
        </div>
      </div>

      <div class="mobile-card-actions">
        <Button
          icon="pi pi-chart-bar"
          label="Трафик"
          size="small"
          severity="secondary"
          outlined
          @click="$emit('showTraffic', user)"
        />
        <Button
          icon="pi pi-link"
          label="Ссылка"
          size="small"
          severity="secondary"
          outlined
          @click="$emit('copyUserLink', user)"
        />
        <template v-if="!user.remnawave">
          <Button
            v-if="user.is_blocked"
            icon="pi pi-lock-open"
            label="Разблокировать"
            size="small"
            severity="success"
            outlined
            @click="$emit('unblock', user)"
          />
          <Button
            v-else
            icon="pi pi-ban"
            label="Блок"
            size="small"
            severity="warn"
            outlined
            @click="$emit('block', user)"
          />
          <Button
            icon="pi pi-trash"
            label="Удалить"
            size="small"
            severity="danger"
            outlined
            @click="$emit('confirmDelete', $event, user)"
          />
        </template>
        <span v-else class="remnawave-managed-text">Только просмотр</span>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { peerSeverity, isOnline, remnawaveSeverity } from '../../utils/status'
import { fmtHandshake, fmtDate, fmtBytes, formatDateTime } from '../../utils/format'
import type { User, Node } from '../../api'

defineProps<{
  users: User[]
  loading: boolean
  readyNodes: Node[]
}>()

defineEmits<{
  block: [user: User]
  unblock: [user: User]
  confirmDelete: [event: Event, user: User]
  showTraffic: [user: User]
  copyUserLink: [user: User]
  downloadConfig: [user: User, node: Node]
  downloadConfigZip: [user: User]
  showQr: [user: User, node: Node]
}>()

function syncSeverity(status: string): string {
  if (status === 'synced') return 'success'
  if (status === 'syncing' || status === 'pending' || status === 'queued') return 'warn'
  if (status === 'failed' || status === 'error') return 'danger'
  return 'secondary'
}

function trafficLimitLabel(limitBytes: number): string {
  return limitBytes > 0 ? fmtBytes(limitBytes) : 'без лимита'
}

function formatDateTimeOrDash(iso: string | null): string {
  return iso ? formatDateTime(iso) : '—'
}
</script>

<style scoped>
.dim {
  color: var(--p-surface-500);
}

.peer-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  white-space: nowrap;
}

.remnawave-label {
  color: var(--p-primary-500);
  font-size: 0.75rem;
  font-weight: 600;
}

.remnawave-managed-text {
  color: var(--p-surface-500);
  font-size: 0.78rem;
  font-style: italic;
}

.remnawave-source {
  color: var(--p-primary-500);
}

.mobile-remnawave-info {
  margin-bottom: 0.5rem;
}

.mobile-remnawave-head {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.mobile-remnawave-grid {
  display: grid;
  gap: 0.5rem;
}

.mobile-remnawave-grid > div {
  display: grid;
  gap: 0.1rem;
}

.mobile-remnawave-grid span {
  color: var(--p-surface-500);
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.mobile-remnawave-grid code {
  word-break: break-all;
}

.mobile-remnawave-error b {
  color: var(--p-red-500);
}

.mobile-peer-list,
.mobile-config-grid {
  display: grid;
  gap: 0.45rem;
}

.mobile-card-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
  margin-top: 1rem;
}

.mobile-card-list {
  display: none;
}

@media (max-width: 760px) {
  .mobile-card-list {
    display: grid;
    gap: 0.75rem;
  }
}
</style>
