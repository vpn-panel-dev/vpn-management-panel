<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="title"
    modal
    class="qr-dialog"
  >
    <div class="qr-shell">
      <div class="qr-tabs">
        <button
          v-for="tab in qrTabs"
          :key="tab.key"
          @click="$emit('update:tab', tab.key)"
          :class="{ 'qr-tab-active': currentTab === tab.key }"
        >
          {{ $t(tab.labelKey) }}
        </button>
      </div>
      <div class="qr-stage">
        <template v-if="currentTab === 'wg'">
          <img v-if="srcWg" :src="srcWg" :alt="$t('qrDialog.qrWgAlt')" />
          <ProgressSpinner v-else style="width: 60px; height: 60px" />
        </template>
        <template v-else>
          <img v-if="srcAmnezia" :src="srcAmnezia" :alt="$t('qrDialog.qrVpnAlt')" />
          <ProgressSpinner v-else style="width: 60px; height: 60px" />
        </template>
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import Dialog from 'primevue/dialog'
import ProgressSpinner from 'primevue/progressspinner'
import { qrTabs } from '../../composables/useDownloads'

defineProps<{
  visible: boolean
  title: string
  srcWg: string
  srcAmnezia: string
  currentTab: 'wg' | 'amnezia'
}>()

defineEmits<{
  'update:visible': [value: boolean]
  'update:tab': [value: 'wg' | 'amnezia']
}>()
</script>

<style scoped>
.qr-dialog {
  width: min(440px, 94vw);
}

.qr-shell {
  padding-top: 0.25rem;
}

.qr-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.35rem;
  margin-bottom: 1rem;
  padding: 0.35rem;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-panel);
}

.qr-tabs button {
  min-height: 2.35rem;
  border: 0;
  border-radius: var(--app-radius-sm);
  cursor: pointer;
  background: transparent;
  color: var(--app-text-muted);
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.qr-tab-active {
  background: var(--app-accent) !important;
  color: #07111f !important;
}

.qr-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 340px;
  padding: 1rem;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background: #fff;
}

.qr-stage img {
  display: block;
  width: min(340px, 76vw);
  height: min(340px, 76vw);
}
</style>
