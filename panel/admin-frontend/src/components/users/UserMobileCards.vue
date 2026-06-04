<template>
  <div class="mobile-card-list">
    <div v-if="loading" class="mobile-empty">{{ $t('userMobile.loading') }}</div>
    <div v-else-if="!users.length" class="mobile-empty">{{ $t('userMobile.empty') }}</div>
    <article v-for="user in users" v-else :key="user.id" class="mobile-user-card">
      <div class="mobile-card-head">
        <div>
          <div class="mobile-card-title">{{ user.name }}</div>
          <div class="mobile-card-sub">{{ user.vpn_ip || $t('userMobile.ipNotAssigned') }}</div>
        </div>
        <div class="mobile-card-tags">
          <Tag
            :severity="user.is_blocked ? 'danger' : 'success'"
            :value="
              user.is_blocked ? $t('userMobile.statusBlocked') : $t('userMobile.statusActive')
            "
            style="font-size: 0.75rem"
          />
          <Tag
            :severity="user.online ? 'success' : 'secondary'"
            :value="user.online ? $t('userMobile.statusOnline') : $t('userMobile.statusOffline')"
            style="font-size: 0.72rem"
          />
          <Tag v-if="user.remnawave" severity="info" value="Remnawave" style="font-size: 0.72rem" />
          <Tag
            v-if="user.remnawave"
            :severity="syncSeverity(user.remnawave.sync_status)"
            :value="user.remnawave.sync_status"
            style="font-size: 0.72rem"
          />
          <Tag
            v-if="user.remnawave"
            severity="secondary"
            :value="$t('userMobile.readonly')"
            style="font-size: 0.72rem"
          />
        </div>
      </div>

      <div v-if="user.remnawave" class="mobile-remnawave-info">
        <div class="mobile-remnawave-head">
          <span class="remnawave-label">{{ $t('userMobile.managedByRemnawave') }}</span>
          <Tag
            :severity="remnawaveSeverity(user.remnawave.status)"
            :value="user.remnawave.status"
            style="font-size: 0.72rem"
          />
        </div>
        <div class="mobile-remnawave-grid">
          <div>
            <span>{{ $t('userMobile.labelUuid') }}</span>
            <code :title="user.remnawave.uuid">{{ user.remnawave.uuid }}</code>
          </div>
          <div>
            <span>{{ $t('userMobile.labelSource') }}</span>
            <b class="remnawave-source">{{ $t('userMobile.sourceRemnawave') }}</b>
          </div>
          <div>
            <span>{{ $t('userMobile.labelUsername') }}</span>
            <b>{{ user.remnawave.username }}</b>
          </div>
          <div>
            <span>{{ $t('userMobile.labelExpires') }}</span>
            <b>{{ fmtDate(user.remnawave.expire_at) }}</b>
          </div>
          <div>
            <span>{{ $t('userMobile.labelTrafficLimit') }}</span>
            <b>{{ trafficLimitLabel(user.remnawave.traffic_limit_bytes) }}</b>
          </div>
          <div>
            <span>{{ $t('userMobile.labelBlockedReason') }}</span>
            <Tag
              :severity="remnawaveBlockedReasonSeverity(user.remnawave.blocked_reason)"
              :value="remnawaveBlockedReasonLabel(user.remnawave.blocked_reason)"
              style="font-size: 0.72rem"
            />
          </div>
          <div>
            <span>{{ $t('userMobile.labelLastSync') }}</span>
            <b>{{ formatDateTimeOrDash(user.remnawave.last_synced_at) }}</b>
          </div>
          <div>
            <span>{{ $t('userMobile.labelSyncReason') }}</span>
            <b>{{ user.remnawave.sync_reason || '—' }}</b>
          </div>
          <div class="mobile-remnawave-error">
            <span>{{ $t('userMobile.labelSyncError') }}</span>
            <b>{{ user.remnawave.sync_error || '—' }}</b>
          </div>
        </div>
      </div>

      <div class="mobile-local-traffic">
        <span>{{
          user.remnawave ? $t('userMobile.combinedUsage') : $t('userMobile.localUsage')
        }}</span>
        <b v-if="user.remnawave">{{ fmtBytes(user.remnawave.combined_traffic_used_bytes) }}</b>
        <b v-else-if="user.local_traffic">{{ fmtBytes(user.local_traffic.total_bytes) }}</b>
        <b v-else class="dim">—</b>
        <small v-if="user.remnawave">
          {{
            $t('userMobile.localUsageDetail', {
              rw: fmtBytes(user.remnawave.traffic_used_bytes),
              local: fmtBytes(user.remnawave.local_amneziawg_traffic_used_bytes),
            })
          }}
        </small>
        <small v-else>{{ $t('userMobile.standaloneUsage') }}</small>
      </div>

      <div class="mobile-fields">
        <div>
          <span>{{ $t('userMobile.nodes') }}</span>
          <div v-if="user.peers?.length" class="mobile-peer-list">
            <span v-for="p in user.peers" :key="p.node_id" class="peer-chip">
              <span
                :title="
                  p.last_handshake
                    ? $t('userMobile.lastHandshake', {
                        time: fmtHandshake(p.last_handshake),
                        endpoint: p.endpoint ? ` · ${p.endpoint}` : '',
                      })
                    : $t('userMobile.neverConnected')
                "
                :style="{
                  display: 'inline-block',
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: p.online ? 'var(--p-green-400)' : 'var(--p-surface-400)',
                  flexShrink: 0,
                }"
              />
              <Tag
                :severity="peerSeverity(p.status)"
                :value="p.node_name"
                style="font-size: 0.72rem"
              />
              <code v-if="p.endpoint" class="peer-endpoint">{{ p.endpoint }}</code>
            </span>
          </div>
          <b v-else class="dim">{{ $t('userMobile.noNodes') }}</b>
        </div>
        <div>
          <span>{{ $t('userMobile.configs') }}</span>
          <div v-if="readyNodes.length" class="mobile-config-grid">
            <Button
              v-for="n in readyNodes"
              :key="n.id"
              :label="n.name"
              icon="pi pi-download"
              size="small"
              severity="secondary"
              outlined
              @click="$emit('downloadConfig', user, n)"
            />
            <Button
              v-for="n in readyNodes"
              :key="`qr-${n.id}`"
              :label="`${n.name} QR`"
              icon="pi pi-qrcode"
              size="small"
              severity="secondary"
              outlined
              @click="$emit('showQr', user, n)"
            />
            <Button
              v-if="readyNodes.length > 1"
              label="ZIP"
              icon="pi pi-file-export"
              size="small"
              severity="secondary"
              outlined
              @click="$emit('downloadConfigZip', user)"
            />
          </div>
          <b v-else class="dim">{{ $t('userMobile.noNodes') }}</b>
        </div>
      </div>

      <div class="mobile-card-actions">
        <Button
          icon="pi pi-chart-bar"
          :label="$t('userMobile.traffic')"
          size="small"
          severity="secondary"
          outlined
          @click="$emit('showTraffic', user)"
        />
        <Button
          icon="pi pi-link"
          :label="$t('userMobile.link')"
          size="small"
          severity="secondary"
          outlined
          @click="$emit('copyUserLink', user)"
        />
        <template v-if="!user.remnawave">
          <Button
            v-if="user.is_blocked"
            icon="pi pi-lock-open"
            :label="$t('userMobile.unblock')"
            size="small"
            severity="success"
            outlined
            @click="$emit('unblock', user)"
          />
          <Button
            v-else
            icon="pi pi-ban"
            :label="$t('userMobile.blockAction')"
            size="small"
            severity="warn"
            outlined
            @click="$emit('block', user)"
          />
          <Button
            icon="pi pi-trash"
            :label="$t('userMobile.delete')"
            size="small"
            severity="danger"
            outlined
            @click="$emit('confirmDelete', $event, user)"
          />
        </template>
        <span v-else class="remnawave-managed-text">{{ $t('userMobile.viewOnly') }}</span>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import {
  peerSeverity,
  remnawaveSeverity,
  remnawaveBlockedReasonLabel,
  remnawaveBlockedReasonSeverity,
} from '../../utils/status'
import { fmtHandshake, fmtDate, fmtBytes, formatDateTime } from '../../utils/format'
import type { User, Node } from '../../api'

const { t } = useI18n()

defineProps<{
  users: User[]
  loading: boolean
  readyNodes: Node[]
}>()

defineEmits<{
  block: [user: User]
  unblock: [user: User]
  confirmDelete: [event: Event, user: User]
  showTraffic: [user: User]
  copyUserLink: [user: User]
  downloadConfig: [user: User, node: Node]
  downloadConfigZip: [user: User]
  showQr: [user: User, node: Node]
}>()

function syncSeverity(status: string): string {
  if (status === 'synced') return 'success'
  if (status === 'syncing' || status === 'pending' || status === 'queued') return 'warn'
  if (status === 'failed' || status === 'error') return 'danger'
  return 'secondary'
}

function trafficLimitLabel(limitBytes: number): string {
  return limitBytes > 0 ? fmtBytes(limitBytes) : t('userDetail.noLimit')
}

function formatDateTimeOrDash(iso: string | null): string {
  return iso ? formatDateTime(iso) : '—'
}
</script>

<style scoped>
.dim {
  color: var(--p-surface-500);
}

.peer-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  white-space: nowrap;
}

.peer-endpoint {
  font-size: 0.7rem;
}

.remnawave-label {
  color: var(--p-primary-500);
  font-size: 0.75rem;
  font-weight: 600;
}

.remnawave-managed-text {
  color: var(--p-surface-500);
  font-size: 0.78rem;
  font-style: italic;
}

.remnawave-source {
  color: var(--p-primary-500);
}

.mobile-remnawave-info {
  margin-bottom: 0.5rem;
}

.mobile-remnawave-head {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.mobile-remnawave-grid {
  display: grid;
  gap: 0.5rem;
}

.mobile-remnawave-grid > div {
  display: grid;
  gap: 0.1rem;
}

.mobile-remnawave-grid span {
  color: var(--p-surface-500);
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.mobile-remnawave-grid code {
  word-break: break-all;
}

.mobile-remnawave-error b {
  color: var(--p-red-500);
}

.mobile-local-traffic {
  display: grid;
  gap: 0.15rem;
  margin-bottom: 0.75rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--app-border);
  border-radius: 14px;
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-primary-50));
}

.mobile-local-traffic span {
  color: var(--app-text-soft);
  font-size: 0.68rem;
  font-weight: 750;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.mobile-local-traffic b {
  color: var(--app-text);
  font-size: 0.92rem;
}

.mobile-local-traffic small {
  color: var(--app-text-muted);
  font-size: 0.74rem;
}

.mobile-peer-list,
.mobile-config-grid {
  display: grid;
  gap: 0.45rem;
}

.mobile-card-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.5rem;
  margin-top: 1rem;
}

.mobile-card-list {
  display: none;
}

@media (max-width: 760px) {
  .mobile-card-list {
    display: grid;
    gap: 0.75rem;
  }
}
</style>
