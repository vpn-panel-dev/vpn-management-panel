<template>
  <div>
    <div class="page-header">
      <h2>Remnawave</h2>
    </div>

    <div v-if="loading" class="settings-card muted-card">Загрузка настроек…</div>
    <div v-else-if="!loaded" class="settings-card muted-card">Не удалось загрузить настройки.</div>

    <form v-else class="settings-card settings-form" @submit.prevent="saveSettings">
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
              data-testid="remnawave-api-token"
            />
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

      <section v-if="settings" data-testid="remnawave-status">
        <div class="section-header">
          <h3>Статус</h3>
        </div>

        <div class="status-grid">
          <div class="field">
            <label>Последняя проверка</label>
            <span v-if="settings.last_tested_at" class="status-value">
              {{ formatDate(settings.last_tested_at) }}
              <Tag
                :severity="settings.last_test_status === 'success' ? 'success' : 'danger'"
                :value="settings.last_test_status === 'success' ? 'OK' : 'Ошибка'"
                class="status-tag"
              />
            </span>
            <span v-else class="dim">—</span>
          </div>
          <div v-if="settings.last_test_error" class="field wide-field">
            <label>Ошибка проверки</label>
            <code class="error-text">{{ settings.last_test_error }}</code>
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
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import InputSwitch from 'primevue/inputswitch'
import { remnawaveApi } from '../api/remnawave'
import type { RemnawaveSettings } from '../api/types'

const toast = useToast()

const loading = ref(true)
const loaded = ref(false)
const saving = ref(false)
const testing = ref(false)
const syncing = ref(false)
const settings = ref<RemnawaveSettings | null>(null)

const webhookUrl = `${window.location.origin}/api/remnawave/webhook`

const form = reactive({
  base_url: '',
  api_token: '',
  webhook_secret: '',
  polling_enabled: false,
  polling_interval_seconds: 300,
})

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

async function loadSettings() {
  loading.value = true
  try {
    const data = await remnawaveApi.getRemnawaveSettings()
    if (data) {
      settings.value = data
      form.base_url = data.base_url ?? ''
      form.polling_enabled = data.polling_enabled
      form.polling_interval_seconds = data.polling_interval_seconds
      loaded.value = true
    } else {
      loaded.value = false
    }
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
    if (data) {
      settings.value = data
      form.api_token = ''
      form.webhook_secret = ''
    }
    toast.add({
      severity: 'success',
      summary: 'Сохранено',
      detail: 'Настройки Remnawave обновлены.',
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
  try {
    const result = await remnawaveApi.syncRemnawaveUsers()
    if (result) {
      toast.add({
        severity: 'success',
        summary: 'Синхронизация запущена',
        detail: `Операция ${result.operation_id}`,
        life: 4000,
      })
    }
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e instanceof Error ? e.message : 'Не удалось запустить синхронизацию',
      life: 4000,
    })
  } finally {
    syncing.value = false
  }
}

onMounted(loadSettings)
</script>
