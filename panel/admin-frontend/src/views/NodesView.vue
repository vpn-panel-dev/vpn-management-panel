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

    <NodeFormDialog v-model:visible="showAdd" :submitting="submitting" @add-node="addNode" />

    <ConfirmPopup />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'
import ConfirmPopup from 'primevue/confirmpopup'
import NodeTable from '../components/nodes/NodeTable.vue'
import NodeMobileCards from '../components/nodes/NodeMobileCards.vue'
import NodeFormDialog from '../components/nodes/NodeFormDialog.vue'
import { useNodes } from '../composables/useNodes'

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

const onlineCount = computed(() => nodes.value.filter((node) => node.online).length)
const errorCount = computed(() => nodes.value.filter((node) => node.last_error).length)
</script>
