<template>
  <div class="row-actions">
    <Button
      icon="pi pi-refresh"
      :label="mobile ? $t('nodeActions.applyConfig') : undefined"
      text
      size="small"
      severity="secondary"
      :outlined="mobile"
      :title="mobile ? undefined : $t('nodeActions.applyConfig')"
      :loading="provisioning"
      @click="$emit('provision')"
    />
    <Button
      icon="pi pi-pencil"
      :label="mobile ? $t('nodeActions.settings') : undefined"
      text
      size="small"
      severity="secondary"
      :outlined="mobile"
      :title="mobile ? undefined : $t('nodeActions.settings')"
      :aria-label="mobile ? undefined : $t('nodeActions.settings')"
      as="router-link"
      :to="`/nodes/${nodeId}/settings`"
    />
    <Button
      icon="pi pi-trash"
      :label="mobile ? $t('nodeActions.delete') : undefined"
      :severity="'danger'"
      text
      size="small"
      :outlined="mobile"
      :title="mobile ? undefined : $t('nodeActions.delete')"
      :aria-label="mobile ? undefined : $t('nodeActions.delete')"
      @click="$emit('confirmDelete', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button'

defineProps<{
  nodeId: string
  provisioning: boolean
  mobile?: boolean
}>()

defineEmits<{
  provision: []
  confirmDelete: [event: Event]
}>()
</script>

<style scoped>
.row-actions {
  display: flex;
  align-items: center;
  gap: 0.15rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.row-actions :deep(.p-button) {
  border-radius: 999px;
}
</style>
