<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="title"
    modal
    style="width: min(980px, 96vw)"
  >
    <div v-if="loading" class="traffic-loading">
      <ProgressSpinner style="width: 50px; height: 50px" />
    </div>
    <div v-else class="traffic-dialog">
      <section v-if="user?.remnawave" class="traffic-section traffic-section--combined">
        <div class="traffic-section-head">
          <div>
            <div class="traffic-kicker">Combined usage</div>
            <h3>Amnezia local accounting</h3>
            <p>Imported Remnawave usage plus measured local AmneziaWG usage.</p>
          </div>
          <Tag class="traffic-tag" severity="success" value="combined" />
        </div>

        <div class="traffic-metrics">
          <article class="traffic-metric">
            <span class="traffic-metric-label">Remnawave imported</span>
            <strong class="traffic-metric-value">{{
              fmtBytes(user.remnawave.traffic_used_bytes)
            }}</strong>
          </article>
          <article class="traffic-metric">
            <span class="traffic-metric-label">Local AmneziaWG</span>
            <strong class="traffic-metric-value">{{
              fmtBytes(user.remnawave.local_amneziawg_traffic_used_bytes)
            }}</strong>
          </article>
          <article class="traffic-metric traffic-metric--accent">
            <span class="traffic-metric-label">Combined</span>
            <strong class="traffic-metric-value">{{
              fmtBytes(user.remnawave.combined_traffic_used_bytes)
            }}</strong>
          </article>
          <article class="traffic-metric traffic-metric--wide">
            <span class="traffic-metric-label">Limit comparison</span>
            <span class="traffic-metric-note">{{ combinedLimitLabel(user) }}</span>
          </article>
        </div>
      </section>

      <section class="traffic-section traffic-section--legacy">
        <div class="traffic-section-head">
          <div>
            <div class="traffic-kicker">Legacy traffic</div>
            <h3>30-дневный график RX / TX</h3>
            <p>Старый импортированный трафик оставлен без изменений.</p>
          </div>
          <Tag class="traffic-tag" severity="secondary" value="legacy" />
        </div>

        <template v-if="data.length">
          <div class="traffic-legend">
            <span class="traffic-legend-item">
              <span class="traffic-legend-swatch traffic-legend-swatch--rx" />
              Загрузка (RX)
            </span>
            <span class="traffic-legend-item">
              <span class="traffic-legend-swatch traffic-legend-swatch--tx" />
              Отдача (TX)
            </span>
          </div>

          <div class="traffic-chart">
            <div
              v-for="pt in data"
              :key="pt.day"
              class="traffic-bar-column"
              :title="`${pt.day}\nRX: ${fmtBytes(pt.rx_bytes)}\nTX: ${fmtBytes(pt.tx_bytes)}`"
            >
              <div class="traffic-bar-stack">
                <div
                  class="traffic-bar traffic-bar--rx"
                  :style="{
                    height: maxVal
                      ? Math.max(2, Math.round((pt.rx_bytes / maxVal) * 140)) + 'px'
                      : '2px',
                  }"
                />
                <div
                  class="traffic-bar traffic-bar--tx"
                  :style="{
                    height: maxVal
                      ? Math.max(2, Math.round((pt.tx_bytes / maxVal) * 140)) + 'px'
                      : '2px',
                  }"
                />
              </div>
              <span class="traffic-day-label">{{ pt.day.slice(5) }}</span>
            </div>
          </div>

          <div class="traffic-summary">
            Всего за период: RX {{ fmtBytes(data.reduce((s, p) => s + p.rx_bytes, 0)) }} · TX
            {{ fmtBytes(data.reduce((s, p) => s + p.tx_bytes, 0)) }}
          </div>
        </template>

        <div v-else class="traffic-empty">Данных пока нет</div>
      </section>

      <section class="traffic-section">
        <div class="traffic-section-head">
          <div>
            <div class="traffic-kicker">Local AmneziaWG usage</div>
            <h3>Local AmneziaWG usage</h3>
            <p>Отдельно от legacy/imported usage: итоги, дни и ноды.</p>
          </div>
          <Tag class="traffic-tag" severity="info" value="local" />
        </div>

        <div class="traffic-metrics">
          <article class="traffic-metric">
            <span class="traffic-metric-label">RX</span>
            <strong class="traffic-metric-value">{{ fmtBytes(localTotals?.rx_bytes ?? 0) }}</strong>
          </article>
          <article class="traffic-metric">
            <span class="traffic-metric-label">TX</span>
            <strong class="traffic-metric-value">{{ fmtBytes(localTotals?.tx_bytes ?? 0) }}</strong>
          </article>
          <article class="traffic-metric">
            <span class="traffic-metric-label">Total</span>
            <strong class="traffic-metric-value">{{
              fmtBytes(localTotals?.total_bytes ?? 0)
            }}</strong>
          </article>
          <article class="traffic-metric traffic-metric--wide">
            <span class="traffic-metric-label">Updated</span>
            <span class="traffic-metric-note">{{
              formatDateTimeOrDash(localTotals?.updated_at)
            }}</span>
          </article>
        </div>

        <div class="traffic-note">Эти значения не входят в legacy chart.</div>

        <div class="traffic-breakdown-grid">
          <article class="traffic-panel">
            <div class="traffic-panel-head">
              <h4>По дням</h4>
              <span>{{ localDaily.length }} записей</span>
            </div>
            <div v-if="localDaily.length" class="traffic-table-wrap">
              <table class="traffic-table">
                <thead>
                  <tr>
                    <th>День</th>
                    <th>RX</th>
                    <th>TX</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in localDaily" :key="row.day">
                    <td>{{ formatDay(row.day) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.rx_bytes) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.tx_bytes) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.total_bytes) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="traffic-empty traffic-empty--inline">Нет дневных записей</div>
          </article>

          <article class="traffic-panel">
            <div class="traffic-panel-head">
              <h4>По нодам</h4>
              <span>{{ localNodes.length }} узлов</span>
            </div>
            <div v-if="localNodes.length" class="traffic-table-wrap">
              <table class="traffic-table">
                <thead>
                  <tr>
                    <th>Нода</th>
                    <th>RX</th>
                    <th>TX</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in localNodes" :key="row.node_id">
                    <td>
                      <div class="traffic-node">
                        <span class="traffic-node-name">{{ row.node_name }}</span>
                        <code class="traffic-node-id">{{ row.node_id }}</code>
                      </div>
                    </td>
                    <td class="traffic-value">{{ fmtBytes(row.rx_bytes) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.tx_bytes) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.total_bytes) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="traffic-empty traffic-empty--inline">Нет данных по нодам</div>
          </article>

          <article class="traffic-panel traffic-panel--wide">
            <div class="traffic-panel-head">
              <h4>По нодам / по дням</h4>
              <span>{{ localNodesDaily.length }} записей</span>
            </div>
            <div v-if="localNodesDaily.length" class="traffic-table-wrap">
              <table class="traffic-table">
                <thead>
                  <tr>
                    <th>Нода</th>
                    <th>День</th>
                    <th>RX</th>
                    <th>TX</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in localNodesDaily" :key="`${row.node_id}-${row.day}`">
                    <td>
                      <div class="traffic-node">
                        <span class="traffic-node-name">{{ row.node_name }}</span>
                        <code class="traffic-node-id">{{ row.node_id }}</code>
                      </div>
                    </td>
                    <td>{{ formatDay(row.day) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.rx_bytes) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.tx_bytes) }}</td>
                    <td class="traffic-value">{{ fmtBytes(row.total_bytes) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="traffic-empty traffic-empty--inline">
              Нет детальных записей по нодам
            </div>
          </article>
        </div>
      </section>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import Dialog from 'primevue/dialog'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import { fmtBytes, formatDateTime } from '../../utils/format'
import type {
  LocalAmneziawgUsageDailyTotals,
  LocalAmneziawgUsageNodeDailyTotals,
  LocalAmneziawgUsageNodeTotals,
  LocalAmneziawgUsageTotals,
  TrafficPoint,
  User,
} from '../../api'

defineProps<{
  visible: boolean
  title: string
  loading: boolean
  data: TrafficPoint[]
  maxVal: number
  user: User | null
  localTotals: LocalAmneziawgUsageTotals | null
  localDaily: LocalAmneziawgUsageDailyTotals[]
  localNodes: LocalAmneziawgUsageNodeTotals[]
  localNodesDaily: LocalAmneziawgUsageNodeDailyTotals[]
}>()

defineEmits<{
  'update:visible': [value: boolean]
}>()

function formatDateTimeOrDash(iso: string | null | undefined): string {
  return iso ? formatDateTime(iso) : '—'
}

function formatDay(day: string): string {
  const [year, month, date] = day.split('-')
  if (!year || !month || !date) return day
  return `${date}.${month}.${year}`
}

function combinedLimitLabel(user: User): string {
  const limit = user.remnawave?.traffic_limit_bytes ?? 0
  if (limit <= 0 || !user.remnawave) return 'Без лимита'
  return `${fmtBytes(user.remnawave.combined_traffic_used_bytes)} / ${fmtBytes(limit)}`
}
</script>

<style scoped>
.traffic-dialog {
  display: grid;
  gap: 1rem;
  padding-top: 0.25rem;
}

.traffic-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 24rem;
}

.traffic-section {
  display: grid;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid var(--app-border);
  border-radius: 18px;
  background: color-mix(in srgb, var(--app-shell-solid) 94%, var(--p-primary-50));
}

.traffic-section--legacy {
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-primary-100));
}

.traffic-section--combined {
  background: color-mix(in srgb, var(--app-shell-solid) 88%, var(--p-green-100));
}

.traffic-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.traffic-kicker {
  color: var(--app-text-soft);
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.traffic-section-head h3 {
  margin: 0.15rem 0 0;
  color: var(--app-text);
  font-size: 1rem;
  font-weight: 750;
}

.traffic-section-head p {
  margin: 0.25rem 0 0;
  color: var(--app-text-muted);
  font-size: 0.83rem;
}

.traffic-tag {
  flex-shrink: 0;
}

.traffic-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  font-size: 0.78rem;
  color: var(--app-text-muted);
}

.traffic-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.traffic-legend-swatch {
  width: 0.75rem;
  height: 0.75rem;
  border-radius: 0.25rem;
}

.traffic-legend-swatch--rx {
  background: var(--p-primary-400);
}

.traffic-legend-swatch--tx {
  background: var(--p-green-400);
}

.traffic-chart {
  display: flex;
  align-items: flex-end;
  gap: 0.35rem;
  height: 160px;
  overflow-x: auto;
  padding-bottom: 0.25rem;
}

.traffic-bar-column {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  min-width: 18px;
}

.traffic-bar-stack {
  display: flex;
  align-items: flex-end;
  gap: 1px;
  height: 140px;
}

.traffic-bar {
  width: 8px;
  border-radius: 2px 2px 0 0;
}

.traffic-bar--rx {
  background: var(--p-primary-400);
}

.traffic-bar--tx {
  background: var(--p-green-400);
}

.traffic-day-label {
  height: 36px;
  color: var(--app-text-soft);
  font-size: 0.62rem;
  writing-mode: vertical-lr;
  transform: rotate(180deg);
}

.traffic-summary,
.traffic-note {
  color: var(--app-text-muted);
  font-size: 0.8rem;
}

.traffic-empty {
  padding: 1rem 0;
  color: var(--app-text-soft);
  text-align: center;
}

.traffic-empty--inline {
  padding: 0.8rem;
  border: 1px dashed var(--app-border);
  border-radius: 14px;
  background: color-mix(in srgb, var(--app-shell-solid) 90%, var(--p-primary-50));
}

.traffic-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.75rem;
}

.traffic-metric {
  display: grid;
  gap: 0.35rem;
  min-height: 5.5rem;
  padding: 0.9rem;
  border: 1px solid var(--app-border);
  border-radius: 16px;
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-primary-50));
}

.traffic-metric--wide {
  grid-column: 1 / -1;
}

.traffic-metric--accent {
  border-color: color-mix(in srgb, var(--p-green-400) 50%, var(--app-border));
  background: color-mix(in srgb, var(--app-shell-solid) 80%, var(--p-green-100));
}

.traffic-metric-label {
  color: var(--app-text-soft);
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.traffic-metric-value {
  color: var(--app-text);
  font-size: 1.02rem;
  font-weight: 750;
}

.traffic-metric-note {
  color: var(--app-text-muted);
  font-size: 0.84rem;
  overflow-wrap: anywhere;
}

.traffic-breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.traffic-panel {
  display: grid;
  gap: 0.75rem;
  min-width: 0;
  padding: 0.9rem;
  border: 1px solid var(--app-border);
  border-radius: 16px;
  background: color-mix(in srgb, var(--app-shell-solid) 95%, var(--p-primary-50));
}

.traffic-panel--wide {
  grid-column: 1 / -1;
}

.traffic-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.traffic-panel-head h4 {
  margin: 0;
  color: var(--app-text);
  font-size: 0.92rem;
  font-weight: 750;
}

.traffic-panel-head span {
  color: var(--app-text-soft);
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.traffic-table-wrap {
  overflow: auto;
  max-height: 18rem;
  border: 1px solid var(--app-border);
  border-radius: 14px;
  background: var(--app-shell-solid);
}

.traffic-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.traffic-table th,
.traffic-table td {
  padding: 0.7rem 0.75rem;
  border-bottom: 1px solid var(--app-border);
  vertical-align: top;
}

.traffic-table thead th {
  position: sticky;
  top: 0;
  background: color-mix(in srgb, var(--app-shell-solid) 86%, var(--p-primary-50));
  color: var(--app-text-soft);
  font-size: 0.68rem;
  font-weight: 750;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  z-index: 1;
}

.traffic-table tbody tr:hover {
  background: var(--app-hover);
}

.traffic-table tbody tr:last-child td {
  border-bottom: none;
}

.traffic-table th:first-child,
.traffic-table td:first-child {
  text-align: left;
}

.traffic-table th:not(:first-child),
.traffic-table td:not(:first-child) {
  text-align: right;
}

.traffic-node {
  display: grid;
  gap: 0.15rem;
}

.traffic-node-name {
  color: var(--app-text);
  font-weight: 700;
}

.traffic-node-id {
  word-break: break-all;
}

.traffic-value {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 900px) {
  .traffic-metrics,
  .traffic-breakdown-grid {
    grid-template-columns: 1fr;
  }
}
</style>
