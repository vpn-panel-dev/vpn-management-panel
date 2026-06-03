<template>
  <DataTable
    class="desktop-table"
    :value="nodes"
    :loading="loading"
    v-model:expandedRows="expandedRows"
    dataKey="id"
    size="small"
  >
    <template #empty>
      <div class="table-empty-state">
        <i class="pi pi-server" />
        <strong>Флот нод пуст</strong>
        <span>Добавьте первый VPN-узел, чтобы начать провижонинг пользователей.</span>
      </div>
    </template>

    <Column expander style="width: 3rem" />

    <Column field="name" header="Название">
      <template #body="{ data }">
        <div class="node-name-cell">
          <span class="node-name">{{ data.name }}</span>
          <Tag
            :severity="data.online ? 'success' : 'danger'"
            :value="data.online ? 'online' : 'offline'"
            class="status-tag"
          />
          <i
            v-if="data.last_error"
            class="pi pi-exclamation-circle node-error-icon"
            :title="data.last_error"
          />
        </div>
      </template>
    </Column>

    <Column field="url" header="URL агента">
      <template #body="{ data }">
        <code>{{ data.url }}</code>
      </template>
    </Column>

    <Column header="Эндпоинт">
      <template #body="{ data }">
        <code v-if="data.server_endpoint">{{ data.server_endpoint }}</code>
        <span v-else class="dim">—</span>
      </template>
    </Column>

    <Column header="Метаданные">
      <template #body="{ data }">
        <div v-if="data.server_public_key" class="metadata-list">
          <code :title="data.server_public_key">{{ data.server_public_key.slice(0, 18) }}…</code>
          <span class="meta-chip">port {{ data.listen_port }}</span>
          <span class="meta-chip">Jc {{ data.jc }} · {{ data.jmin }}–{{ data.jmax }}ms</span>
          <span v-if="data.mtu" class="meta-chip">MTU {{ data.mtu }}</span>
          <span v-if="data.i1" class="meta-chip muted-chip">I✓</span>
        </div>
        <Tag v-else severity="warn" value="ожидание sync" class="status-tag" />
      </template>
    </Column>

    <Column header="Действия" style="width: 12rem; text-align: right">
      <template #body="{ data }">
        <NodeActions
          :node-id="data.id"
          :provisioning="provisioning[data.id]"
          @provision="$emit('provision', data)"
          @confirm-delete="$emit('confirmDelete', $event, data)"
        />
      </template>
    </Column>

    <template #expansion="{ data }">
      <div class="node-expansion">
        <DataTable
          :value="peersCache[data.id]"
          :loading="!peersCache[data.id]"
          size="small"
          class="peer-table"
        >
          <template #empty>Пиры ещё не назначены.</template>
          <Column field="user_name" header="Пользователь" />
          <Column field="vpn_ip" header="IP">
            <template #body="{ data: p }">
              <code>{{ p.vpn_ip }}/32</code>
            </template>
          </Column>
          <Column field="status" header="Статус">
            <template #body="{ data: p }">
              <div class="node-peer-status">
                <span
                  :style="{
                    display: 'inline-block',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: p.online ? 'var(--p-green-400)' : 'var(--p-surface-400)',
                    flexShrink: 0,
                  }"
                />
                <Tag
                  :severity="peerSeverity(p.status)"
                  :value="p.status"
                  style="font-size: 0.75rem"
                />
              </div>
            </template>
          </Column>
          <Column header="Endpoint">
            <template #body="{ data: p }">
              <code v-if="p.endpoint">{{ p.endpoint }}</code>
              <span v-else class="dim">—</span>
            </template>
          </Column>
        </DataTable>
      </div>
    </template>
  </DataTable>
</template>

<script setup lang="ts">
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import NodeActions from './NodeActions.vue'
import { peerSeverity } from '../../utils/status'
import type { Node, NodePeer } from '../../api'

const expandedRows = defineModel<Record<string, boolean>>('expandedRows', { required: true })

defineProps<{
  nodes: Node[]
  loading: boolean
  peersCache: Record<string, NodePeer[] | null>
  provisioning: Record<string, boolean>
}>()

defineEmits<{
  provision: [node: Node]
  confirmDelete: [event: Event, node: Node]
}>()
</script>

<style scoped>
.node-name-cell {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.node-name {
  font-weight: 900;
  letter-spacing: 0.01em;
}

.node-error-icon {
  color: var(--p-red-500);
  font-size: 0.9rem;
  cursor: help;
}

.node-peer-status {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.node-expansion {
  padding: 0.9rem 1rem;
}

.peer-table {
  max-width: 720px;
  box-shadow: none;
}
</style>
