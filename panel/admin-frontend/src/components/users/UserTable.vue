<template>
  <section class="users-workspace-card" data-testid="users-list">
    <div v-if="loading" class="user-list-skeleton" data-testid="users-loading">
      <div v-for="n in 8" :key="n" class="user-skeleton-row" />
    </div>

    <div v-else-if="!users.length" class="table-empty-state" data-testid="users-empty">
      <i class="pi pi-users" />
      <strong>{{ emptyTitle }}</strong>
      <span>{{ emptyText }}</span>
    </div>

    <div v-else class="compact-user-list" role="list">
      <article
        v-for="user in users"
        :key="user.id"
        :class="['compact-user-row', { 'compact-user-row--selected': selectedId === user.id }]"
        role="listitem"
        @click="$emit('select', user)"
      >
        <div class="user-primary">
          <div class="user-avatar" :class="{ 'user-avatar--rw': user.remnawave }">
            {{ initials(user.name) }}
          </div>
          <div class="user-identity">
            <button type="button" class="user-name-button" @click.stop="$emit('select', user)">
              {{ user.name }}
            </button>
            <div class="user-subline">
              <code v-if="user.vpn_ip">{{ user.vpn_ip }}</code>
              <span v-else class="dim">{{ $t('userTable.ipNotAssigned') }}</span>
              <span>•</span>
              <span>{{ $t('userTable.nodesCount', { count: user.peers.length }) }}</span>
            </div>
          </div>
        </div>

        <div class="user-state-stack">
          <Tag
            :severity="user.is_blocked ? 'danger' : 'success'"
            :value="user.is_blocked ? $t('userTable.statusBlocked') : $t('userTable.statusActive')"
            class="status-tag"
          />
          <Tag
            :severity="user.online ? 'success' : 'secondary'"
            :value="user.online ? $t('userTable.statusOnline') : $t('userTable.statusOffline')"
            class="status-tag"
          />
          <Tag
            v-if="user.remnawave"
            severity="info"
            :value="$t('userTable.readonlyExternal')"
            class="status-tag"
          />
        </div>

        <div class="user-signal-block">
          <div class="signal-title">{{ sourceLabel(user) }}</div>
          <div class="signal-meta">
            <template v-if="user.remnawave">
              <span>{{ user.remnawave.username }}</span>
              <Tag
                :severity="syncSeverity(user.remnawave.sync_status, user.remnawave.sync_error)"
                :value="
                  user.remnawave.sync_error ? $t('userTable.syncError') : user.remnawave.sync_status
                "
                class="status-tag"
              />
            </template>
            <template v-else>{{ $t('userTable.localUser') }}</template>
          </div>
        </div>

        <div class="user-usage-block">
          <span>{{ usageLabel(user) }}</span>
          <strong>{{ usageValue(user) }}</strong>
        </div>

        <div class="user-next-actions" @click.stop>
          <Button
            icon="pi pi-link"
            size="small"
            text
            rounded
            severity="secondary"
            :title="$t('userTable.copyLink')"
            :aria-label="$t('userTable.copyLink')"
            @click="$emit('copyUserLink', user)"
          />
          <Button
            icon="pi pi-qrcode"
            size="small"
            text
            rounded
            severity="secondary"
            :title="$t('userTable.openDetails')"
            :aria-label="$t('userTable.openDetails')"
            @click="$emit('select', user)"
          />
          <Button
            icon="pi pi-angle-right"
            size="small"
            text
            rounded
            severity="secondary"
            :title="$t('userTable.details')"
            :aria-label="$t('userTable.details')"
            @click="$emit('select', user)"
          />
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import { fmtBytes, fmtDate } from '../../utils/format'
import type { User } from '../../api'

const { t } = useI18n()

defineProps<{
  users: User[]
  loading: boolean
  selectedId: string | null
  emptyTitle: string
  emptyText: string
}>()

defineEmits<{
  select: [user: User]
  copyUserLink: [user: User]
}>()

function initials(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

function sourceLabel(user: User): string {
  if (!user.remnawave) return t('userTable.localUser')
  const expires = user.remnawave.expire_at
    ? ` · ${t('userTable.expires', { date: fmtDate(user.remnawave.expire_at) })}`
    : ''
  return `${t('userTable.remnawaveUser')}${expires}`
}

function usageLabel(user: User): string {
  return user.remnawave ? t('userTable.combinedTraffic') : t('userTable.localTraffic')
}

function usageValue(user: User): string {
  if (user.remnawave) return fmtBytes(user.remnawave.combined_traffic_used_bytes)
  return user.local_traffic ? fmtBytes(user.local_traffic.total_bytes) : '—'
}

function syncSeverity(status: string, error: string | null): string {
  if (error || status === 'failed' || status === 'error') return 'danger'
  if (status === 'synced') return 'success'
  return 'warn'
}
</script>

<style scoped>
.users-workspace-card {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-lg);
  background: linear-gradient(
    180deg,
    var(--app-shell-solid),
    color-mix(in srgb, var(--app-shell-solid) 92%, var(--app-bg-accent))
  );
  box-shadow: var(--app-shadow);
}

.compact-user-list,
.user-list-skeleton {
  display: grid;
}

.compact-user-row {
  display: grid;
  grid-template-columns:
    minmax(14rem, 1.6fr) minmax(8rem, 0.75fr) minmax(12rem, 1fr) minmax(8rem, 0.75fr)
    auto;
  gap: 0.85rem;
  align-items: center;
  min-width: 0;
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--app-border);
  cursor: pointer;
  transition:
    background 0.15s,
    box-shadow 0.15s;
}

.compact-user-row:last-child {
  border-bottom: 0;
}

.compact-user-row:hover,
.compact-user-row--selected {
  background: var(--app-hover);
  box-shadow: inset 3px 0 0 var(--app-accent);
}

.user-primary {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.75rem;
  align-items: center;
  min-width: 0;
}

.user-avatar {
  display: grid;
  place-items: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 14px;
  background: color-mix(in srgb, var(--app-cyan) 20%, var(--app-shell-solid));
  border: 1px solid color-mix(in srgb, var(--app-cyan) 34%, var(--app-border));
  color: var(--app-text);
  font-size: 0.78rem;
  font-weight: 900;
}

.user-avatar--rw {
  background: color-mix(in srgb, var(--app-accent) 20%, var(--app-shell-solid));
  border-color: color-mix(in srgb, var(--app-accent) 38%, var(--app-border));
}

.user-identity,
.user-signal-block,
.user-usage-block {
  min-width: 0;
}

.user-name-button {
  max-width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--app-text);
  cursor: pointer;
  font: inherit;
  font-weight: 900;
  overflow: hidden;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-subline,
.signal-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
  margin-top: 0.25rem;
  color: var(--app-text-muted);
  font-size: 0.78rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-state-stack {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.signal-title,
.user-usage-block span {
  color: var(--app-text-soft);
  font-size: 0.68rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.user-usage-block strong {
  display: block;
  margin-top: 0.2rem;
  color: var(--app-text);
  font-size: 0.95rem;
}

.user-next-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.15rem;
}

.user-skeleton-row {
  height: 4.45rem;
  border-bottom: 1px solid var(--app-border);
  background: linear-gradient(
    90deg,
    transparent,
    color-mix(in srgb, var(--app-accent) 10%, transparent),
    transparent
  );
  animation: pulse-row 1.25s ease-in-out infinite;
}

@keyframes pulse-row {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 0.9;
  }
}

@media (max-width: 1120px) {
  .compact-user-row {
    grid-template-columns: minmax(14rem, 1fr) minmax(9rem, 0.7fr) auto;
  }

  .user-signal-block,
  .user-usage-block {
    display: none;
  }
}

@media (max-width: 760px) {
  .compact-user-row {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
  }

  .user-signal-block,
  .user-usage-block {
    display: block;
  }

  .user-next-actions {
    justify-content: flex-start;
  }
}
</style>
