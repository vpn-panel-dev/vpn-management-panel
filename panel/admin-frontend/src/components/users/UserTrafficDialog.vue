<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="title"
    modal
    style="width: 640px"
  >
    <div v-if="loading" style="text-align: center; padding: 2rem">
      <ProgressSpinner style="width: 50px; height: 50px" />
    </div>
    <div
      v-else-if="!data?.length"
      style="color: var(--p-surface-500); text-align: center; padding: 2rem"
    >
      Данных пока нет
    </div>
    <div v-else>
      <div
        style="
          display: flex;
          gap: 1rem;
          margin-bottom: 0.75rem;
          font-size: 0.8rem;
          color: var(--p-surface-500);
        "
      >
        <span style="display: flex; align-items: center; gap: 0.3rem">
          <span
            style="
              display: inline-block;
              width: 12px;
              height: 12px;
              background: var(--p-primary-400);
              border-radius: 2px;
            "
          ></span>
          Загрузка (RX)
        </span>
        <span style="display: flex; align-items: center; gap: 0.3rem">
          <span
            style="
              display: inline-block;
              width: 12px;
              height: 12px;
              background: var(--p-green-400);
              border-radius: 2px;
            "
          ></span>
          Отдача (TX)
        </span>
      </div>
      <div
        style="
          display: flex;
          align-items: flex-end;
          gap: 3px;
          height: 160px;
          overflow-x: auto;
          padding-bottom: 4px;
        "
      >
        <div
          v-for="pt in data"
          :key="pt.day"
          style="
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            min-width: 18px;
            flex: 1;
          "
          :title="`${pt.day}\nRX: ${fmtBytes(pt.rx_bytes)}\nTX: ${fmtBytes(pt.tx_bytes)}`"
        >
          <div style="display: flex; align-items: flex-end; gap: 1px; height: 140px">
            <div
              :style="{
                width: '8px',
                height: maxVal
                  ? Math.max(2, Math.round((pt.rx_bytes / maxVal) * 140)) + 'px'
                  : '2px',
                background: 'var(--p-primary-400)',
                borderRadius: '2px 2px 0 0',
              }"
            />
            <div
              :style="{
                width: '8px',
                height: maxVal
                  ? Math.max(2, Math.round((pt.tx_bytes / maxVal) * 140)) + 'px'
                  : '2px',
                background: 'var(--p-green-400)',
                borderRadius: '2px 2px 0 0',
              }"
            />
          </div>
          <span
            style="
              font-size: 0.62rem;
              color: var(--p-surface-500);
              writing-mode: vertical-lr;
              transform: rotate(180deg);
              height: 36px;
            "
          >
            {{ pt.day.slice(5) }}
          </span>
        </div>
      </div>
      <div style="margin-top: 0.75rem; font-size: 0.8rem; color: var(--p-surface-500)">
        Всего за период: RX
        {{ fmtBytes(data.reduce((s, p) => s + p.rx_bytes, 0)) }} · TX
        {{ fmtBytes(data.reduce((s, p) => s + p.tx_bytes, 0)) }}
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import Dialog from 'primevue/dialog'
import ProgressSpinner from 'primevue/progressspinner'
import { fmtBytes } from '../../utils/format'
import type { TrafficPoint } from '../../api'

defineProps<{
  visible: boolean
  title: string
  loading: boolean
  data: TrafficPoint[] | null
  maxVal: number
}>()

defineEmits<{
  'update:visible': [value: boolean]
}>()
</script>
