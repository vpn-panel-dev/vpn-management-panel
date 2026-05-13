<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="title"
    modal
    style="width: 420px"
  >
    <div style="padding: 0.5rem 0">
      <div
        style="
          display: flex;
          gap: 0;
          border: 1px solid var(--p-surface-200);
          border-radius: 8px;
          overflow: hidden;
          margin-bottom: 1.25rem;
        "
      >
        <button
          v-for="tab in qrTabs"
          :key="tab.key"
          @click="$emit('update:tab', tab.key)"
          :style="{
            flex: 1,
            padding: '0.5rem',
            border: 'none',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '0.82rem',
            transition: 'background 0.15s, color 0.15s',
            background: currentTab === tab.key ? 'var(--p-primary-500)' : 'transparent',
            color: currentTab === tab.key ? '#fff' : 'var(--p-surface-500)',
          }"
        >
          {{ tab.label }}
        </button>
      </div>
      <div
        style="
          text-align: center;
          min-height: 340px;
          display: flex;
          align-items: center;
          justify-content: center;
        "
      >
        <template v-if="currentTab === 'wg'">
          <img v-if="srcWg" :src="srcWg" style="width: 340px; height: 340px; display: block" />
          <ProgressSpinner v-else style="width: 60px; height: 60px" />
        </template>
        <template v-else>
          <img
            v-if="srcAmnezia"
            :src="srcAmnezia"
            style="width: 340px; height: 340px; display: block"
          />
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
