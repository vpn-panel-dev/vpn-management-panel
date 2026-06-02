<template>
  <DataTable class="desktop-table" :value="users" :loading="loading" dataKey="id" size="small">
    <template #empty>Нет пользователей.</template>

    <Column field="name" header="Имя" style="min-width: 10rem">
      <template #body="{ data }">
        <div class="user-name-cell">
          <span class="user-name">{{ data.name }}</span>
          <Tag
            :severity="data.online ? 'success' : 'secondary'"
            :value="data.online ? 'online' : 'offline'"
            style="font-size: 0.72rem"
          />
        </div>
      </template>
    </Column>

    <Column header="VPN IP" style="width: 9rem">
      <template #body="{ data }">
        <code v-if="data.vpn_ip">{{ data.vpn_ip }}</code>
        <span v-else class="dim">—</span>
      </template>
    </Column>

    <Column header="Статус" style="width: 8rem">
      <template #body="{ data }">
        <Tag
          :severity="data.is_blocked ? 'danger' : 'success'"
          :value="data.is_blocked ? 'заблокирован' : 'активен'"
          style="font-size: 0.75rem"
        />
      </template>
    </Column>

    <Column header="Источник" style="min-width: 24rem">
      <template #body="{ data }">
        <template v-if="data.remnawave">
          <div class="remnawave-meta-card">
            <div class="remnawave-meta-head">
              <Tag severity="info" value="Remnawave" style="font-size: 0.72rem" />
              <Tag
                :severity="syncSeverity(data.remnawave.sync_status)"
                :value="data.remnawave.sync_status"
                style="font-size: 0.72rem"
              />
              <Tag severity="secondary" value="только просмотр" style="font-size: 0.72rem" />
            </div>

            <div class="remnawave-meta-grid">
              <div class="remnawave-meta-item">
                <span class="meta-label">UUID</span>
                <code :title="data.remnawave.uuid">{{ data.remnawave.uuid }}</code>
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Источник</span>
                <span class="remnawave-source">Remnawave</span>
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Username</span>
                <span>{{ data.remnawave.username }}</span>
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Статус</span>
                <Tag
                  :severity="remnawaveSeverity(data.remnawave.status)"
                  :value="data.remnawave.status"
                  style="font-size: 0.72rem"
                />
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Истекает</span>
                <span>{{ fmtDate(data.remnawave.expire_at) }}</span>
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Лимит трафика</span>
                <span>{{ trafficLimitLabel(data.remnawave.traffic_limit_bytes) }}</span>
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Причина блокировки</span>
                <Tag
                  :severity="remnawaveBlockedReasonSeverity(data.remnawave.blocked_reason)"
                  :value="remnawaveBlockedReasonLabel(data.remnawave.blocked_reason)"
                  style="font-size: 0.72rem"
                />
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Последняя синхронизация</span>
                <span>{{ formatDateTimeOrDash(data.remnawave.last_synced_at) }}</span>
              </div>
              <div class="remnawave-meta-item">
                <span class="meta-label">Причина sync</span>
                <span>{{ data.remnawave.sync_reason || '—' }}</span>
              </div>
              <div class="remnawave-meta-item remnawave-meta-item--error">
                <span class="meta-label">Ошибка sync</span>
                <span>{{ data.remnawave.sync_error || '—' }}</span>
              </div>
            </div>
          </div>
        </template>
        <span v-else class="dim">—</span>
      </template>
    </Column>

    <Column header="Traffic usage" style="width: 13rem">
      <template #body="{ data }">
        <div v-if="data.remnawave" class="local-traffic-card">
          <span class="meta-label">Combined</span>
          <strong class="local-traffic-value">{{
            fmtBytes(data.remnawave.combined_traffic_used_bytes)
          }}</strong>
          <span class="local-traffic-note">
            Remnawave {{ fmtBytes(data.remnawave.traffic_used_bytes) }} + Local
            {{ fmtBytes(data.remnawave.local_amneziawg_traffic_used_bytes) }}
          </span>
        </div>
        <div v-else-if="data.local_traffic" class="local-traffic-card">
          <span class="meta-label">Local</span>
          <strong class="local-traffic-value">{{
            fmtBytes(data.local_traffic.total_bytes)
          }}</strong>
          <span class="local-traffic-note">Standalone local usage</span>
        </div>
        <span v-else class="dim">—</span>
      </template>
    </Column>

    <Column header="Ноды">
      <template #body="{ data }">
        <span v-if="!data.peers?.length" class="dim">нет</span>
        <span v-for="p in data.peers" :key="p.node_id" class="peer-chip">
          <span
            :title="
              p.last_handshake
                ? `Последний хендшейк: ${fmtHandshake(p.last_handshake)}${
                    p.endpoint ? ` · ${p.endpoint}` : ''
                  }`
                : 'Никогда не подключался'
            "
            :style="{
              display: 'inline-block',
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: p.online ? 'var(--p-green-400)' : 'var(--p-surface-400)',
              flexShrink: 0,
            }"
          />
          <Tag :severity="peerSeverity(p.status)" :value="p.node_name" style="font-size: 0.72rem" />
          <code v-if="p.endpoint" class="peer-endpoint">{{ p.endpoint }}</code>
        </span>
      </template>
    </Column>

    <Column header="Конфиги">
      <template #body="{ data }">
        <span v-if="!readyNodes.length" class="dim">нет нод</span>
        <template v-else>
          <span
            v-for="n in readyNodes"
            :key="n.id"
            style="margin-right: 0.4rem; white-space: nowrap"
          >
            <Button
              :label="n.name"
              icon="pi pi-download"
              size="small"
              text
              severity="secondary"
              class="compact-action"
              @click="$emit('downloadConfig', data, n)"
            />
            <Button
              icon="pi pi-qrcode"
              size="small"
              text
              severity="secondary"
              class="compact-action"
              title="Показать QR"
              aria-label="Показать QR"
              @click="$emit('showQr', data, n)"
            />
          </span>
          <Button
            v-if="readyNodes.length > 1"
            label="ZIP"
            icon="pi pi-file-export"
            size="small"
            text
            severity="secondary"
            class="compact-action"
            @click="$emit('downloadConfigZip', data)"
          />
        </template>
      </template>
    </Column>

    <Column header="Действия" style="width: 15rem; white-space: nowrap; text-align: right">
      <template #body="{ data }">
        <div v-if="data.remnawave" class="row-actions remnawave-managed">
          <Button
            icon="pi pi-chart-bar"
            size="small"
            text
            rounded
            severity="secondary"
            title="Показать трафик"
            aria-label="Показать трафик"
            @click="$emit('showTraffic', data)"
          />
          <Button
            icon="pi pi-link"
            size="small"
            text
            rounded
            severity="secondary"
            title="Скопировать ссылку пользователя"
            @click="$emit('copyUserLink', data)"
          />
          <Tag severity="secondary" value="только просмотр" style="font-size: 0.72rem" />
        </div>
        <div v-else class="row-actions">
          <Button
            icon="pi pi-chart-bar"
            size="small"
            text
            rounded
            severity="secondary"
            title="Показать трафик"
            aria-label="Показать трафик"
            @click="$emit('showTraffic', data)"
          />
          <Button
            icon="pi pi-link"
            size="small"
            text
            rounded
            severity="secondary"
            title="Скопировать ссылку пользователя"
            @click="$emit('copyUserLink', data)"
          />
          <Button
            v-if="data.is_blocked"
            label="Разблокировать"
            icon="pi pi-lock-open"
            size="small"
            text
            severity="success"
            class="compact-action"
            @click="$emit('unblock', data)"
          />
          <Button
            v-else
            label="Блок"
            icon="pi pi-ban"
            size="small"
            text
            severity="warn"
            class="compact-action"
            @click="$emit('block', data)"
          />
          <Button
            icon="pi pi-trash"
            size="small"
            text
            rounded
            severity="danger"
            title="Удалить пользователя"
            aria-label="Удалить пользователя"
            @click="$emit('confirmDelete', $event, data)"
          />
        </div>
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import {
  peerSeverity,
  remnawaveSeverity,
  remnawaveBlockedReasonLabel,
  remnawaveBlockedReasonSeverity,
} from '../../utils/status'
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

.user-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.user-name {
  font-weight: 650;
}

.peer-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin-right: 0.45rem;
  white-space: nowrap;
}

.peer-endpoint {
  font-size: 0.7rem;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 0.15rem;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.compact-action {
  padding: 0.2rem 0.5rem !important;
  font-size: 0.78rem !important;
}

.remnawave-managed-text {
  color: var(--p-surface-500);
  font-size: 0.78rem;
  font-style: italic;
}

.remnawave-meta-card {
  display: grid;
  gap: 0.5rem;
}

.remnawave-meta-head {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.remnawave-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.35rem 0.75rem;
}

.remnawave-meta-item {
  display: grid;
  gap: 0.1rem;
}

.remnawave-meta-item--error {
  grid-column: 1 / -1;
}

.meta-label {
  color: var(--p-surface-500);
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.remnawave-source {
  color: var(--p-primary-500);
  font-weight: 600;
}

.remnawave-meta-item code {
  word-break: break-all;
}

.remnawave-meta-item--error span:last-child {
  color: var(--p-red-500);
}

.remnawave-managed {
  gap: 0.45rem;
}

.local-traffic-card {
  display: grid;
  gap: 0.15rem;
}

.local-traffic-value {
  color: var(--app-text);
  font-size: 0.92rem;
}

.local-traffic-note {
  color: var(--p-surface-500);
  font-size: 0.72rem;
}

@media (max-width: 760px) {
  .desktop-table {
    display: none;
  }
}
</style>
