<template>
  <div>
    <div class="page-header">
      <div>
        <span class="page-kicker"><i class="pi pi-server" /> Node fleet</span>
        <h2>Ноды</h2>
        <p class="page-description">
          Провижонинг VPN-узлов, проверка готовности ключей и быстрый доступ к peer-состоянию.
        </p>
        <div class="page-stats">
          <span class="stat-pill"
            ><span>Всего</span><strong>{{ nodes.length }}</strong></span
          >
          <span class="stat-pill"
            ><span>Online</span><strong>{{ onlineCount }}</strong></span
          >
          <span class="stat-pill"
            ><span>Ошибки</span><strong>{{ errorCount }}</strong></span
          >
        </div>
      </div>
      <div class="page-actions">
        <Button label="Добавить ноду" icon="pi pi-plus" @click="openAdd" />
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
