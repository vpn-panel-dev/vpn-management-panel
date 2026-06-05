<template>
  <div>
    <div class="page-header">
      <div>
        <span class="page-kicker"><i class="pi pi-server" /> {{ $t('nodes.kicker') }}</span>
        <h2>{{ $t('nodes.title') }}</h2>
        <p class="page-description">{{ $t('nodes.description') }}</p>
        <div class="page-stats">
          <span class="stat-pill"
            ><span>{{ $t('nodes.total') }}</span
            ><strong>{{ nodes.length }}</strong></span
          >
          <span class="stat-pill"
            ><span>{{ $t('nodes.online') }}</span
            ><strong>{{ onlineCount }}</strong></span
          >
          <span class="stat-pill"
            ><span>{{ $t('nodes.errors') }}</span
            ><strong>{{ errorCount }}</strong></span
          >
        </div>
      </div>
      <div class="page-actions">
        <Button :label="$t('nodes.addNode')" icon="pi pi-plus" @click="openAdd" />
      </div>
    </div>

    <NodeTable
      v-model:expanded-rows="expandedRows"
      :nodes="nodes"
      :loading="loading"
      :peers-cache="peersCache"
      :provisioning="provisioning"
      @provision="provisionNode"
      @confirm-delete="confirmDelete"
    />

    <NodeMobileCards
      :nodes="nodes"
      :loading="loading"
      :provisioning="provisioning"
      @provision="provisionNode"
      @confirm-delete="confirmDelete"
    />

    <section class="ops-card">
      <div class="ops-card-head">
        <div>
          <span class="page-kicker"><i class="pi pi-history" /> {{ $t('operations.kicker') }}</span>
          <h3>{{ $t('operations.title') }}</h3>
        </div>
        <Button :label="$t('operations.refresh')" size="small" text @click="loadOperations" />
      </div>
      <div v-if="!attentionOperations.length" class="dim">{{ $t('operations.empty') }}</div>
      <div v-else class="ops-list">
        <div v-for="operation in attentionOperations" :key="operation.id" class="ops-row">
          <Tag :severity="operationSeverity(operation.status)" :value="operation.status" />
          <code>{{ operation.kind }}</code>
          <span>{{ operation.target_id || operation.target_type || 'all' }}</span>
          <span class="dim">{{ operation.updated_at }}</span>
          <b v-if="operation.error" class="error-text">{{ operation.error }}</b>
        </div>
      </div>
    </section>

    <NodeFormDialog v-model:visible="showAdd" :submitting="submitting" @add-node="addNode" />

    <ConfirmPopup />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import ConfirmPopup from 'primevue/confirmpopup'
import Tag from 'primevue/tag'
import NodeTable from '../components/nodes/NodeTable.vue'
import NodeMobileCards from '../components/nodes/NodeMobileCards.vue'
import NodeFormDialog from '../components/nodes/NodeFormDialog.vue'
import { useNodes } from '../composables/useNodes'
import { operationsApi } from '../api/operations'
import type { AsyncOperation } from '../api/types'
import { operationSeverity } from '../utils/status'

const {
  nodes,
  loading,
  expandedRows,
  peersCache,
  provisioning,
  showAdd,
  submitting,
  provisionNode,
  openAdd,
  addNode,
  confirmDelete,
} = useNodes()

const operations = ref<AsyncOperation[]>([])
const onlineCount = computed(() => nodes.value.filter((node) => node.reachable).length)
const errorCount = computed(
  () => nodes.value.filter((node) => node.last_error || node.last_heartbeat_error).length,
)
const attentionOperations = computed(() =>
  operations.value.filter((operation) =>
    ['running', 'failed', 'failed_by_timeout', 'enqueue_failed'].includes(operation.status),
  ),
)

async function loadOperations() {
  operations.value = (await operationsApi.getOperations(undefined, 50)) || []
}

onMounted(loadOperations)
</script>

<style scoped>
.ops-card {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid var(--p-surface-200);
  border-radius: var(--radius-lg);
  background: var(--p-surface-0);
}

.ops-card-head,
.ops-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.ops-card-head {
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.ops-list {
  display: grid;
  gap: 0.5rem;
}
</style>
