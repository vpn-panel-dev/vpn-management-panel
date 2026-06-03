<template>
  <div class="row-actions">
    <Button
      icon="pi pi-refresh"
      :label="mobile ? 'Применить конфиг' : undefined"
      text
      size="small"
      severity="secondary"
      :outlined="mobile"
      :title="mobile ? undefined : 'Применить конфигурацию'"
      :loading="provisioning"
      @click="$emit('provision')"
    />
    <Button
      icon="pi pi-pencil"
      :label="mobile ? 'Настройки' : undefined"
      text
      size="small"
      severity="secondary"
      :outlined="mobile"
      :title="mobile ? undefined : 'Настройки ноды'"
      :aria-label="mobile ? undefined : 'Настройки ноды'"
      as="router-link"
      :to="`/nodes/${nodeId}/settings`"
    />
    <Button
      icon="pi pi-trash"
      :label="mobile ? 'Удалить' : undefined"
      :severity="'danger'"
      text
      size="small"
      :outlined="mobile"
      :title="mobile ? undefined : 'Удалить ноду'"
      :aria-label="mobile ? undefined : 'Удалить ноду'"
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
