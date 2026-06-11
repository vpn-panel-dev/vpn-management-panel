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
            ><span>{{ $t('nodes.ready') }}</span
            ><strong>{{ readyCount }}</strong></span
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

    <section class="settings-card ops-card">
      <div class="ops-card-head">
        <div class="section-header ops-section-header">
          <span class="page-kicker"><i class="pi pi-history" /> {{ $t('operations.kicker') }}</span>
          <h3>{{ $t('operations.title') }}</h3>
          <p>{{ $t('operations.description') }}</p>
        </div>
        <Button
          :label="$t('operations.refresh')"
          icon="pi pi-refresh"
          size="small"
          severity="secondary"
          outlined
          @click="loadOperations"
        />
      </div>
      <div v-if="!attentionOperations.length" class="muted-card ops-empty">
        {{ $t('operations.empty') }}
      </div>
      <div v-else class="ops-list">
        <article
          v-for="operation in attentionOperations"
          :key="operation.id"
          :class="[
            'ops-item',
            {
              'ops-item--manual': operation.resolution_state === 'needs_manual_action',
              'ops-item--recoverable': operation.resolution_state === 'recoverable',
            },
          ]"
        >
          <div class="ops-item-head">
            <div class="ops-item-title-block">
              <code>{{ operation.kind }}</code>
              <strong class="ops-target">{{
                operation.target_id || operation.target_type || 'all'
              }}</strong>
            </div>
            <div class="ops-tags">
              <Tag :severity="operationSeverity(operation.status)" :value="operation.status" />
              <Tag
                v-if="operation.resolution_state"
                :severity="operationResolutionSeverity(operation.resolution_state)"
                :value="$t(`operations.${operation.resolution_state}`)"
              />
            </div>
          </div>

          <div class="ops-meta-row">
            <span class="ops-meta-label">{{ $t('operations.updatedAt') }}</span>
            <span class="ops-meta-value">{{ formatDateTime(operation.updated_at) }}</span>
          </div>

          <b v-if="operation.error" class="error-text">{{ operation.error }}</b>

          <div v-if="operation.can_retry" class="ops-actions">
            <Button
              :label="$t('operations.retry')"
              size="small"
              severity="secondary"
              outlined
              @click="retryOperation(operation)"
            />
          </div>
        </article>
      </div>
    </section>

    <NodeFormDialog v-model:visible="showAdd" :submitting="submitting" @add-node="addNode" />

    <ConfirmPopup />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Button from 'primevue/button'
import ConfirmPopup from 'primevue/confirmpopup'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'
import { useI18n } from 'vue-i18n'
import NodeTable from '../components/nodes/NodeTable.vue'
import NodeMobileCards from '../components/nodes/NodeMobileCards.vue'
import NodeFormDialog from '../components/nodes/NodeFormDialog.vue'
import { useNodes } from '../composables/useNodes'
import { operationsApi } from '../api/operations'
import type { AsyncOperation } from '../api/types'
import { formatDateTime } from '../utils/format'
import { getNodeStage, operationResolutionSeverity, operationSeverity } from '../utils/status'

const toast = useToast()
const { t } = useI18n()

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
const readyCount = computed(
  () => nodes.value.filter((node) => getNodeStage(node) === 'ready').length,
)
const errorCount = computed(
  () => nodes.value.filter((node) => node.last_error || node.last_heartbeat_error).length,
)
const attentionStatuses = new Set(['running', 'failed', 'failed_by_timeout', 'enqueue_failed'])

function operationKey(operation: AsyncOperation): string {
  return [operation.kind, operation.target_type || 'all', operation.target_id || 'all'].join('::')
}

const attentionOperations = computed(() => {
  const latestByKey = new Map<string, AsyncOperation>()

  for (const operation of operations.value) {
    const key = operationKey(operation)
    if (!latestByKey.has(key)) {
      latestByKey.set(key, operation)
    }
  }

  return [...latestByKey.values()].filter((operation) => attentionStatuses.has(operation.status))
})

async function loadOperations() {
  operations.value = (await operationsApi.getOperations(undefined, 200)) || []
}

async function retryOperation(operation: AsyncOperation) {
  await operationsApi.retryOperation(operation.id)
  toast.add({
    severity: 'success',
    summary: t('operations.retryQueued'),
    detail: `${operation.kind} → ${operation.target_id || operation.target_type || 'all'}`,
    life: 3000,
  })
  await loadOperations()
}

let operationsTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  loadOperations()
  operationsTimer = setInterval(loadOperations, 20_000)
})
onUnmounted(() => {
  if (operationsTimer) clearInterval(operationsTimer)
})
</script>

<style scoped>
.ops-card {
  margin-top: var(--app-space-4);
}

.ops-card-head,
.ops-item-head,
.ops-meta-row,
.ops-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.ops-card-head {
  justify-content: space-between;
  gap: var(--app-space-4);
  margin-bottom: var(--app-space-4);
}

.ops-list {
  display: grid;
  gap: 0.85rem;
}

.ops-section-header {
  margin-bottom: 0;
}

.ops-empty {
  min-height: 0;
  padding: var(--app-space-4);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-md);
  background: color-mix(in srgb, var(--app-shell-solid) 76%, transparent);
}

.ops-item {
  display: grid;
  gap: 0.8rem;
  padding: 1rem 1.05rem;
  border: 1px solid var(--app-border);
  border-radius: 18px;
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-primary-50));
}

.ops-item--recoverable {
  border-color: color-mix(in srgb, var(--app-accent) 28%, var(--app-border));
  background: color-mix(in srgb, var(--app-shell-solid) 90%, var(--p-primary-100));
}

.ops-item--manual {
  border-color: color-mix(in srgb, var(--app-red) 34%, var(--app-border));
  background: color-mix(in srgb, var(--app-shell-solid) 90%, var(--p-red-50));
}

.ops-item-head {
  justify-content: space-between;
  align-items: flex-start;
}

.ops-item-title-block {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex-wrap: wrap;
}

.ops-target {
  color: var(--app-text);
  font-size: 0.92rem;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.ops-tags {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
}

.ops-meta-row {
  gap: 0.45rem;
  color: var(--app-text-muted);
  font-size: 0.82rem;
}

.ops-meta-label {
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--app-text-soft);
}

.ops-meta-value {
  color: var(--app-text-muted);
}

.ops-actions {
  justify-content: flex-end;
}

@media (max-width: 640px) {
  .ops-card-head,
  .ops-item-head {
    align-items: stretch;
  }

  .ops-tags,
  .ops-actions {
    width: 100%;
  }

  .ops-actions :deep(.p-button) {
    width: 100%;
  }
}
</style>
