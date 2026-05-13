<template>
  <div>
    <div class="page-header">
      <h2>Ноды</h2>
      <Button label="Добавить ноду" icon="pi pi-plus" @click="openAdd" />
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
</script>
