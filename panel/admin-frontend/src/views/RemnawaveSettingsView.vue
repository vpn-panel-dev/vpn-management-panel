<template>
  <div>
    <div class="page-header">
      <div>
        <span class="page-kicker"><i class="pi pi-sync" /> Integration control</span>
        <h2>Remnawave</h2>
        <p class="page-description">
          Наблюдение за reconcile, ручная синхронизация пользователей и настройка секретов
          интеграции.
        </p>
      </div>
    </div>

    <div v-if="loading" class="settings-card muted-card">Загрузка настроек…</div>
    <div v-else-if="!loaded" class="settings-card muted-card">Не удалось загрузить настройки.</div>

    <div v-else class="settings-stack">
      <section class="settings-card observability-card" data-testid="remnawave-status">
        <div class="section-header">
          <h3>Обзор синхронизации</h3>
          <p>Состояние Remnawave, reconcile-метрики и ручные операции без раскрытия секретов.</p>
        </div>

        <div v-if="statusLoading" class="muted-card">Загрузка статуса…</div>
        <div v-else-if="statusLoadError" class="muted-card">{{ statusLoadError }}</div>
        <div v-else-if="status" class="metric-grid">
          <article class="metric-card metric-card--state">
            <span class="metric-label">Состояние</span>
            <Tag
              :severity="status.enabled ? 'success' : 'danger'"
              :value="status.enabled ? 'Включён' : 'Выключен'"
              class="status-tag"
            />
            <span class="metric-sub">
              <code v-if="status.base_url">{{ status.base_url }}</code>
              <span v-else class="dim">Base URL не задан</span>
            </span>
          </article>

          <article class="metric-card">
            <span class="metric-label">Импортировано пользователей</span>
            <strong class="metric-value">{{ formatCount(status.imported_users_count) }}</strong>
          </article>

          <article class="metric-card">
            <span class="metric-label">Ожидают node-sync</span>
            <strong class="metric-value">{{ formatCount(status.pending_node_sync_count) }}</strong>
          </article>

          <article class="metric-card">
            <span class="metric-label">Последняя успешная reconcile</span>
            <span v-if="status.last_successful_reconcile_at" class="metric-value">
              {{ formatDate(status.last_successful_reconcile_at) }}
            </span>
            <span v-else class="dim">—</span>
          </article>

          <article class="metric-card">
            <span class="metric-label">Последняя неудачная reconcile</span>
            <span v-if="status.last_failed_reconcile_at" class="metric-value">
              {{ formatDate(status.last_failed_reconcile_at) }}
            </span>
            <span v-else class="dim">—</span>
          </article>

          <article class="metric-card metric-card--wide">
            <span class="metric-label">Последняя ошибка reconcile</span>
            <code v-if="status.last_error" class="metric-code">{{ status.last_error }}</code>
            <span v-else class="dim">—</span>
          </article>

          <article class="metric-card">
            <span class="metric-label">Последняя проверка</span>
            <span v-if="status.last_tested_at" class="metric-inline">
              <Tag
                :severity="remnawaveTestSeverity(status.last_test_status)"
                :value="remnawaveTestLabel(status.last_test_status)"
                class="status-tag"
              />
              <span class="metric-value">{{ formatDate(status.last_tested_at) }}</span>
            </span>
            <span v-else class="dim">—</span>
          </article>

          <article v-if="status.last_test_error" class="metric-card metric-card--wide">
            <span class="metric-label">Ошибка проверки</span>
            <code class="metric-code">{{ status.last_test_error }}</code>
          </article>
        </div>

        <div v-else class="muted-card">Статус пока недоступен.</div>

        <div class="sync-console">
          <div class="section-header sync-header">
            <h3>Точечная синхронизация</h3>
            <p>
              Введите UUID пользователя. Проверка на клиенте только подсказывает формат; backend
              остаётся последней инстанцией.
            </p>
          </div>

          <div class="sync-form">
            <div class="field">
              <label>UUID пользователя</label>
              <InputText
                v-model="syncUserUuid"
                placeholder="11111111-1111-4111-8111-111111111111"
                data-testid="remnawave-user-uuid"
                :class="{ 'p-invalid': syncUserUuidHasValue && !isSyncUserUuidValid }"
              />
              <small
                :class="[
                  'sync-hint',
                  { 'sync-hint--error': syncUserUuidHasValue && !isSyncUserUuidValid },
                ]"
              >
                {{ syncUserUuidHint }}
              </small>
            </div>

            <Button
              type="button"
              label="Синхронизировать пользователя"
              icon="pi pi-refresh"
              severity="secondary"
              :loading="syncingUser"
              :disabled="syncingUser || !syncUserUuidHasValue || !isSyncUserUuidValid"
              data-testid="remnawave-user-sync"
              @click="syncUserByUuid"
            />
          </div>

          <div class="sync-results">
            <article
              v-if="fullSyncResult || fullSyncError"
              :class="['operation-card', { 'operation-card--error': !!fullSyncError }]"
              data-testid="remnawave-full-sync-result"
            >
              <div class="operation-head">
                <span class="operation-title">Последняя полная синхронизация</span>
                <Tag
                  :severity="fullSyncError ? 'danger' : 'success'"
                  :value="fullSyncError ? 'Ошибка' : 'Операция создана'"
                  class="status-tag"
                />
              </div>
              <p v-if="fullSyncError" class="operation-message">{{ fullSyncError }}</p>
              <div v-else class="operation-details">
                <div class="operation-row">
                  <span class="operation-label">Operation ID</span>
                  <code>{{ fullSyncResult?.operation_id }}</code>
                </div>
                <div class="operation-row">
                  <span class="operation-label">Status URL</span>
                  <code>{{ fullSyncResult?.status_url }}</code>
                </div>
              </div>
            </article>

            <article
              v-if="userSyncResult || userSyncError"
              :class="['operation-card', { 'operation-card--error': !!userSyncError }]"
              data-testid="remnawave-user-sync-result"
            >
              <div class="operation-head">
                <span class="operation-title">Последняя синхронизация по UUID</span>
                <Tag
                  :severity="userSyncError ? 'danger' : 'success'"
                  :value="userSyncError ? 'Ошибка' : 'Операция создана'"
                  class="status-tag"
                />
              </div>
              <p v-if="userSyncError" class="operation-message">{{ userSyncError }}</p>
              <div v-else class="operation-details">
                <div class="operation-row">
                  <span class="operation-label">Operation ID</span>
                  <code>{{ userSyncResult?.operation_id }}</code>
                </div>
                <div class="operation-row">
                  <span class="operation-label">Status URL</span>
                  <code>{{ userSyncResult?.status_url }}</code>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <form class="settings-card settings-form" @submit.prevent="saveSettings">
        <section>
          <div class="section-header">
            <h3>Подключение</h3>
            <p>Адрес и токен для связи с Remnawave.</p>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Base URL</label>
              <InputText
                v-model="form.base_url"
                placeholder="https://remnawave.example.com"
                data-testid="remnawave-base-url"
              />
            </div>
            <div class="field">
              <label>API-токен</label>
              <InputText
                v-model="form.api_token"
                :placeholder="settings?.api_token_set ? 'Настроен ✓' : 'Не задан'"
                type="password"
                autocomplete="new-password"
                data-testid="remnawave-api-token"
              />
            </div>
          </div>
        </section>

        <section>
          <div class="section-header">
            <h3>Состояние</h3>
            <p>Включённая интеграция участвует в автоматическом и ручном reconcile.</p>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Включён</label>
              <div class="switch-row">
                <InputSwitch v-model="form.enabled" data-testid="remnawave-enabled" />
                <span class="switch-state">{{ form.enabled ? 'Активно' : 'Выключено' }}</span>
              </div>
            </div>
          </div>
        </section>

        <section>
          <div class="section-header">
            <h3>Webhook</h3>
            <p>Секрет для проверки подписи webhook-уведомлений от Remnawave.</p>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Webhook-секрет</label>
              <InputText
                v-model="form.webhook_secret"
                :placeholder="settings?.webhook_secret_set ? 'Настроен ✓' : 'Не задан'"
                type="password"
                autocomplete="new-password"
                data-testid="remnawave-webhook-secret"
              />
            </div>
            <div class="field">
              <label>URL для подписки</label>
              <code class="webhook-url">{{ webhookUrl }}</code>
            </div>
          </div>
        </section>

        <section>
          <div class="section-header">
            <h3>Поллинг</h3>
            <p>Автоматическая синхронизация пользователей по расписанию.</p>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Включён</label>
              <InputSwitch v-model="form.polling_enabled" />
            </div>
            <div class="field">
              <label>Интервал (сек)</label>
              <InputNumber v-model="form.polling_interval_seconds" :min="60" style="width: 100%" />
            </div>
          </div>
        </section>

        <section>
          <div class="section-header">
            <h3>Local AmneziaWG</h3>
            <p>Очистка raw-сэмплов локального трафика. Значение 0 отключает cleanup.</p>
          </div>

          <div class="form-grid">
            <div class="field">
              <label>Хранение raw-сэмплов (дней)</label>
              <InputNumber
                v-model="form.raw_sample_retention_days"
                :min="0"
                :useGrouping="false"
                style="width: 100%"
                data-testid="local-traffic-retention"
              />
              <small class="section-note">По умолчанию — 90 дней. 0 отключает очистку.</small>
            </div>
            <div class="field">
              <label>Online threshold peer'а (сек)</label>
              <InputNumber
                v-model="form.peer_online_threshold_seconds"
                :min="1"
                :useGrouping="false"
                style="width: 100%"
                data-testid="peer-online-threshold"
              />
              <small class="section-note"
                >Backend считает peer online по последнему handshake.</small
              >
            </div>
          </div>
        </section>

        <div class="settings-actions">
          <Button
            type="submit"
            label="Сохранить"
            icon="pi pi-check"
            :loading="saving"
            data-testid="remnawave-save"
          />
          <Button
            type="button"
            label="Проверить связь"
            icon="pi pi-search"
            severity="secondary"
            :loading="testing"
            data-testid="remnawave-test"
            @click="testConnection"
          />
          <Button
            type="button"
            label="Синхронизировать"
            icon="pi pi-refresh"
            severity="secondary"
            :loading="syncing"
            data-testid="remnawave-sync"
            @click="runSync"
          />
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import InputSwitch from 'primevue/inputswitch'
import { remnawaveApi } from '../api/remnawave'
import type { RemnawaveSettings, RemnawaveStatus, RemnawaveSyncResult } from '../api/types'

const UUID_PATTERN = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/
const countFormatter = new Intl.NumberFormat('ru-RU')

const toast = useToast()

const loading = ref(true)
const loaded = ref(false)
const statusLoading = ref(false)
const statusLoadError = ref<string | null>(null)
const saving = ref(false)
const testing = ref(false)
const syncing = ref(false)
const syncingUser = ref(false)
const settings = ref<RemnawaveSettings | null>(null)
const status = ref<RemnawaveStatus | null>(null)
const fullSyncResult = ref<RemnawaveSyncResult | null>(null)
const fullSyncError = ref<string | null>(null)
const userSyncResult = ref<RemnawaveSyncResult | null>(null)
const userSyncError = ref<string | null>(null)
const syncUserUuid = ref('')

const webhookUrl = `${window.location.origin}/api/remnawave/webhook`

const form = reactive({
  base_url: '',
  enabled: false,
  api_token: '',
  webhook_secret: '',
  polling_enabled: false,
  polling_interval_seconds: 300,
  raw_sample_retention_days: 90,
  peer_online_threshold_seconds: 180,
})

const syncUserUuidValue = computed(() => syncUserUuid.value.trim())
const syncUserUuidHasValue = computed(() => syncUserUuidValue.value.length > 0)
const isSyncUserUuidValid = computed(
  () => !syncUserUuidHasValue.value || UUID_PATTERN.test(syncUserUuidValue.value),
)
const syncUserUuidHint = computed(() => {
  if (!syncUserUuidHasValue.value) {
    return 'Формат UUID: 8-4-4-4-12. Backend проверит значение окончательно.'
  }
  if (!isSyncUserUuidValid.value) {
    return 'UUID должен быть в каноническом формате 8-4-4-4-12.'
  }
  return 'Синхронизация запустит отдельную операцию для выбранного пользователя.'
})

watch(syncUserUuid, () => {
  userSyncResult.value = null
  userSyncError.value = null
})

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

function formatCount(value: number): string {
  return countFormatter.format(value)
}

function remnawaveTestSeverity(statusValue: string | null): string {
  if (statusValue === 'success') return 'success'
  if (statusValue === 'failed') return 'danger'
  return 'secondary'
}

function remnawaveTestLabel(statusValue: string | null): string {
  if (statusValue === 'success') return 'OK'
  if (statusValue === 'failed') return 'Ошибка'
  return '—'
}

function hydrateStatusFromSettings(data: RemnawaveSettings) {
  if (!status.value) return

  status.value.enabled = data.enabled
  status.value.base_url = data.base_url
  status.value.last_tested_at = data.last_tested_at
  status.value.last_test_status = data.last_test_status
  status.value.last_test_error = data.last_test_error
  status.value.last_successful_reconcile_at = data.last_synced_at
}

async function loadStatus() {
  statusLoading.value = true
  statusLoadError.value = null
  try {
    const data = await remnawaveApi.getRemnawaveStatus()
    if (data) {
      status.value = data
      return
    }
    statusLoadError.value = 'Не удалось загрузить статус Remnawave.'
  } catch (e: unknown) {
    statusLoadError.value = e instanceof Error ? e.message : 'Не удалось загрузить статус Remnawave'
  } finally {
    statusLoading.value = false
  }
}

async function loadSettings() {
  loading.value = true
  try {
    const [data, localTrafficSettings] = await Promise.all([
      remnawaveApi.getRemnawaveSettings(),
      remnawaveApi.getLocalTrafficSettings(),
    ])
    if (!data || !localTrafficSettings) {
      throw new Error('Не удалось загрузить настройки')
    }
    settings.value = data
    form.base_url = data.base_url ?? ''
    form.enabled = data.enabled
    form.polling_enabled = data.polling_enabled
    form.polling_interval_seconds = data.polling_interval_seconds
    form.raw_sample_retention_days = localTrafficSettings.raw_sample_retention_days
    form.peer_online_threshold_seconds = localTrafficSettings.peer_online_threshold_seconds
    loaded.value = true
    hydrateStatusFromSettings(data)
    void loadStatus()
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e instanceof Error ? e.message : 'Не удалось загрузить настройки',
      life: 4000,
    })
    loaded.value = false
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      base_url: form.base_url.trim() || null,
      enabled: form.enabled,
      polling_enabled: form.polling_enabled,
      polling_interval_seconds: form.polling_interval_seconds,
    }
    if (form.api_token) {
      payload.api_token = form.api_token
    }
    if (form.webhook_secret) {
      payload.webhook_secret = form.webhook_secret
    }
    const data = await remnawaveApi.updateRemnawaveSettings(payload)
    const localTrafficSettings = await remnawaveApi.updateLocalTrafficSettings({
      raw_sample_retention_days: form.raw_sample_retention_days,
      peer_online_threshold_seconds: form.peer_online_threshold_seconds,
    })
    if (!data || !localTrafficSettings) {
      throw new Error('Не удалось сохранить настройки')
    }
    settings.value = data
    form.api_token = ''
    form.webhook_secret = ''
    hydrateStatusFromSettings(data)
    form.raw_sample_retention_days = localTrafficSettings.raw_sample_retention_days
    form.peer_online_threshold_seconds = localTrafficSettings.peer_online_threshold_seconds
    toast.add({
      severity: 'success',
      summary: 'Сохранено',
      detail: 'Настройки Remnawave и очистки raw-сэмплов обновлены.',
      life: 4000,
    })
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e instanceof Error ? e.message : 'Не удалось сохранить',
      life: 4000,
    })
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testing.value = true
  try {
    const result = await remnawaveApi.testRemnawaveConnection()
    if (result?.success) {
      toast.add({
        severity: 'success',
        summary: 'Связь установлена',
        detail: 'Подключение к Remnawave работает.',
        life: 4000,
      })
    } else {
      toast.add({
        severity: 'error',
        summary: 'Ошибка связи',
        detail: result?.error ?? 'Не удалось подключиться к Remnawave.',
        life: 6000,
      })
    }
    await loadSettings()
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e instanceof Error ? e.message : 'Не удалось проверить связь',
      life: 4000,
    })
  } finally {
    testing.value = false
  }
}

async function runSync() {
  syncing.value = true
  fullSyncError.value = null
  try {
    const result = await remnawaveApi.syncRemnawaveUsers()
    if (result) {
      fullSyncResult.value = result
      toast.add({
        severity: 'success',
        summary: 'Синхронизация запущена',
        detail: `Операция ${result.operation_id}`,
        life: 4000,
      })
    }
  } catch (e: unknown) {
    fullSyncResult.value = null
    fullSyncError.value = e instanceof Error ? e.message : 'Не удалось запустить синхронизацию'
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: fullSyncError.value,
      life: 4000,
    })
  } finally {
    syncing.value = false
  }
}

async function syncUserByUuid() {
  const userUuid = syncUserUuidValue.value
  if (!userUuid || !isSyncUserUuidValid.value) {
    userSyncError.value = 'UUID должен быть в формате 8-4-4-4-12.'
    userSyncResult.value = null
    return
  }

  syncingUser.value = true
  userSyncError.value = null
  userSyncResult.value = null
  try {
    const result = await remnawaveApi.syncRemnawaveUser(userUuid)
    if (result) {
      userSyncResult.value = result
      toast.add({
        severity: 'success',
        summary: 'Синхронизация пользователя запущена',
        detail: `Операция ${result.operation_id}`,
        life: 4000,
      })
    }
  } catch (e: unknown) {
    userSyncError.value =
      e instanceof Error ? e.message : 'Не удалось запустить синхронизацию пользователя'
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: userSyncError.value,
      life: 4000,
    })
  } finally {
    syncingUser.value = false
  }
}

onMounted(loadSettings)
</script>

<style scoped>
.settings-stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.observability-card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 0.85rem;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  min-height: 6rem;
  padding: 1rem;
  border: 1px solid var(--app-border);
  border-radius: 18px;
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-primary-50));
}

.metric-card--state {
  background: color-mix(in srgb, var(--app-shell-solid) 86%, var(--p-primary-100));
}

.metric-card--wide {
  grid-column: 1 / -1;
}

.metric-label {
  font-size: 0.74rem;
  font-weight: 750;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--app-text-soft);
}

.metric-value {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--app-text);
}

.metric-sub {
  color: var(--app-text-muted);
  font-size: 0.86rem;
  overflow-wrap: anywhere;
}

.metric-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.metric-code {
  display: block;
  overflow-wrap: anywhere;
}

.sync-console {
  display: grid;
  gap: 1rem;
  padding-top: 0.25rem;
  border-top: 1px solid var(--app-border);
}

.sync-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.85rem;
  align-items: end;
}

.sync-hint {
  color: var(--app-text-muted);
  font-size: 0.8rem;
}

.sync-hint--error {
  color: var(--p-red-500);
}

.sync-results {
  display: grid;
  gap: 0.75rem;
}

.operation-card {
  display: grid;
  gap: 0.65rem;
  padding: 0.95rem 1rem;
  border: 1px solid var(--app-border);
  border-radius: 16px;
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-primary-50));
}

.operation-card--error {
  border-color: color-mix(in srgb, var(--p-red-500) 32%, var(--app-border));
  background: color-mix(in srgb, var(--app-shell-solid) 92%, var(--p-red-50));
}

.operation-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.operation-title {
  font-weight: 700;
  color: var(--app-text);
}

.operation-message {
  margin: 0;
  color: var(--p-red-500);
  font-size: 0.9rem;
}

.operation-details {
  display: grid;
  gap: 0.55rem;
}

.operation-row {
  display: grid;
  gap: 0.25rem;
}

.operation-label {
  font-size: 0.74rem;
  font-weight: 750;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--app-text-soft);
}

.switch-row {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.switch-state {
  color: var(--app-text-muted);
  font-size: 0.9rem;
}

@media (max-width: 720px) {
  .sync-form {
    grid-template-columns: 1fr;
  }

  .metric-card--wide {
    grid-column: auto;
  }
}
</style>
