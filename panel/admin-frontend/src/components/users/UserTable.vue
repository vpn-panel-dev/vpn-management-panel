<template>
  <DataTable class="desktop-table" :value="users" :loading="loading" dataKey="id" size="small">
    <template #empty>Нет пользователей.</template>

    <Column field="name" header="Имя" style="min-width: 10rem" />

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

    <Column header="Источник" style="width: 10rem">
      <template #body="{ data }">
        <template v-if="data.remnawave">
          <Tag
            :severity="remnawaveSeverity(data.remnawave.status)"
            :value="data.remnawave.status"
            style="font-size: 0.72rem"
          />
          <span
            v-if="data.remnawave.delete_requested_at"
            class="remnawave-warning"
            :title="`Удаляется из Remnawave — ${fmtDate(data.remnawave.delete_requested_at)}`"
          >
            Удаляется
          </span>
          <span v-else class="remnawave-label" :title="remnawaveTooltip(data.remnawave)">
            Remnawave
          </span>
        </template>
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
          <Tag :severity="peerSeverity(p.status)" :value="p.node_name" style="font-size: 0.72rem" />
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
        <div
          v-if="data.remnawave && !data.remnawave.delete_requested_at"
          class="row-actions remnawave-managed"
        >
          <span class="remnawave-managed-text">Управляется Remnawave</span>
        </div>
        <div v-else-if="data.remnawave && data.remnawave.delete_requested_at" class="row-actions">
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
import { peerSeverity, isOnline, remnawaveSeverity, remnawaveTooltip } from '../../utils/status'
import { fmtHandshake, fmtDate } from '../../utils/format'
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
</script>

<style scoped>
.dim {
  color: var(--p-surface-500);
}

.peer-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  margin-right: 0.45rem;
  white-space: nowrap;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 0.15rem;
  justify-content: flex-end;
}

.compact-action {
  padding: 0.2rem 0.5rem !important;
  font-size: 0.78rem !important;
}

.remnawave-label {
  color: var(--p-primary-500);
  font-size: 0.75rem;
  font-weight: 600;
  margin-left: 0.35rem;
}

.remnawave-warning {
  color: var(--p-red-500);
  font-size: 0.75rem;
  font-weight: 600;
  margin-left: 0.35rem;
}

.remnawave-managed-text {
  color: var(--p-surface-500);
  font-size: 0.78rem;
  font-style: italic;
}

@media (max-width: 760px) {
  .desktop-table {
    display: none;
  }
}
</style>
