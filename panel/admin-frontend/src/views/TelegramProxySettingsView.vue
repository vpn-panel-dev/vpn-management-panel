<template>
  <section class="page-shell telegram-proxy-page">
    <div class="page-header">
      <div>
        <p class="page-kicker">{{ t('telegramProxy.kicker') }}</p>
        <h2>{{ t('telegramProxy.title') }}</h2>
        <p class="page-description">{{ t('telegramProxy.description') }}</p>
      </div>
    </div>

    <Message v-if="loadError" severity="error" :closable="false">{{ loadError }}</Message>

    <div class="telegram-proxy-grid">
      <TelegramProxySettingsCard
        v-model:enabled="form.enabled"
        v-model:port="form.port"
        v-model:primary-node-id="form.primaryNodeId"
        v-model:public-host="form.publicHost"
        v-model:secret="form.secret"
        :busy="busy"
        :saving="saving"
        :applying="applying"
        :disabling="disabling"
        :rotating="rotating"
        :node-options="nodeOptions"
        :enabled-tag-label="enabledTagLabel"
        :enabled-tag-severity="enabledTagSeverity"
        :secret-tag-label="secretTagLabel"
        :secret-tag-severity="secretTagSeverity"
        :secret-hint="secretHint"
        @generate-secret="generateSecret"
        @rotate-secret="rotateSecret"
        @save-settings="saveSettings"
        @apply-settings="applySettings"
        @disable-settings="disableSettings"
      />

      <TelegramProxyStatusCard :status="status" :nodes="nodes" @copy-link="copyPublicLink" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from 'primevue/usetoast'
import Message from 'primevue/message'
import TelegramProxySettingsCard from '../components/telegram-proxy/TelegramProxySettingsCard.vue'
import TelegramProxyStatusCard from '../components/telegram-proxy/TelegramProxyStatusCard.vue'
import { nodesApi } from '../api/nodes'
import { telegramProxyApi } from '../api/telegramProxy'
import type { Node, TelegramProxySettingsUpdate, TelegramProxyStatus } from '../api/types'

interface ProxyForm {
  enabled: boolean
  port: number | null
  primaryNodeId: string | null
  publicHost: string
  secret: string
}

const toast = useToast()
const { t } = useI18n()

const loadError = ref<string | null>(null)
const loading = ref(true)
const saving = ref(false)
const applying = ref(false)
const disabling = ref(false)
const rotating = ref(false)
const status = ref<TelegramProxyStatus | null>(null)
const nodes = ref<Node[]>([])

const form = reactive<ProxyForm>({
  enabled: false,
  port: null,
  primaryNodeId: null,
  publicHost: '',
  secret: '',
})

const busy = computed(
  () => loading.value || saving.value || applying.value || disabling.value || rotating.value,
)
const nodeOptions = computed(() =>
  nodes.value.map((node) => ({ label: node.name, value: node.id })),
)
const enabledTagSeverity = computed(() => (form.enabled ? 'success' : 'secondary'))
const enabledTagLabel = computed(() =>
  form.enabled ? t('telegramProxy.enabledOn') : t('telegramProxy.enabledOff'),
)
const secretConfigured = computed(() => status.value?.settings.secret_set ?? false)
const secretDraft = computed(() => form.secret.trim().length > 0)
const secretTagSeverity = computed(() =>
  secretDraft.value || secretConfigured.value ? 'success' : 'warn',
)
const secretTagLabel = computed(() =>
  secretDraft.value
    ? t('telegramProxy.secretDraft')
    : secretConfigured.value
      ? t('telegramProxy.secretConfigured')
      : t('telegramProxy.secretMissing'),
)
const secretHint = computed(() => {
  if (secretDraft.value) return t('telegramProxy.secretDraftHint')
  if (secretConfigured.value) return t('telegramProxy.secretConfiguredHint')
  return t('telegramProxy.secretMissingHint')
})

function showError(detail: unknown, fallback: string) {
  toast.add({
    severity: 'error',
    summary: t('toasts.error'),
    detail: detail instanceof Error ? detail.message : fallback,
    life: 4000,
  })
}

function hydrateFormFromStatus(data: TelegramProxyStatus) {
  form.enabled = data.settings.enabled
  form.port = data.settings.port
  form.primaryNodeId = data.settings.primary_node_id
  form.publicHost = ''
  form.secret = ''
}

async function loadStatusAndNodes() {
  loading.value = true
  loadError.value = null
  try {
    const [proxyStatus, nodeList] = await Promise.all([
      telegramProxyApi.getTelegramProxyStatus(),
      nodesApi.getNodes(),
    ])
    if (!proxyStatus || !nodeList) throw new Error(t('telegramProxy.loadError'))
    status.value = proxyStatus
    nodes.value = nodeList
    hydrateFormFromStatus(proxyStatus)
  } catch (error: unknown) {
    const fallback = t('telegramProxy.loadError')
    loadError.value = error instanceof Error ? error.message : fallback
    showError(error, fallback)
  } finally {
    loading.value = false
  }
}

async function refreshStatus() {
  try {
    const proxyStatus = await telegramProxyApi.getTelegramProxyStatus()
    if (!proxyStatus) throw new Error(t('telegramProxy.loadError'))
    status.value = proxyStatus
    hydrateFormFromStatus(proxyStatus)
  } catch (error: unknown) {
    showError(error, t('telegramProxy.loadError'))
  }
}

async function saveSettings() {
  if (form.port === null) {
    showError(new Error(''), t('telegramProxy.portRequired'))
    return
  }
  saving.value = true
  try {
    const payload: TelegramProxySettingsUpdate = {
      enabled: form.enabled,
      port: form.port,
      primary_node_id: form.primaryNodeId,
      public_host: form.publicHost.trim() || null,
      ...(form.secret.trim() ? { secret: form.secret.trim() } : {}),
    }
    const data = await telegramProxyApi.updateTelegramProxySettings(payload)
    if (!data) throw new Error(t('telegramProxy.saveError'))
    const primaryNodeState = status.value?.primary_node_state ?? null
    status.value = { settings: data, primary_node_state: primaryNodeState, links: data.links }
    hydrateFormFromStatus(status.value)
    toast.add({ severity: 'success', summary: t('telegramProxy.saveSuccess'), life: 2500 })
  } catch (error: unknown) {
    showError(error, t('telegramProxy.saveError'))
  } finally {
    saving.value = false
  }
}

async function applySettings() {
  applying.value = true
  try {
    const result = await telegramProxyApi.applyTelegramProxy()
    if (!result) throw new Error(t('telegramProxy.applyError'))
    toast.add({
      severity: 'success',
      summary: t('telegramProxy.applySuccess'),
      detail: `Operation ${result.operation_id}`,
      life: 3000,
    })
    await refreshStatus()
  } catch (error: unknown) {
    showError(error, t('telegramProxy.applyError'))
  } finally {
    applying.value = false
  }
}

async function disableSettings() {
  disabling.value = true
  try {
    const result = await telegramProxyApi.disableTelegramProxy()
    if (!result) throw new Error(t('telegramProxy.disableError'))
    toast.add({
      severity: 'success',
      summary: t('telegramProxy.disableSuccess'),
      detail: `Operation ${result.operation_id}`,
      life: 3000,
    })
    await refreshStatus()
  } catch (error: unknown) {
    showError(error, t('telegramProxy.disableError'))
  } finally {
    disabling.value = false
  }
}

async function rotateSecret() {
  rotating.value = true
  try {
    const result = await telegramProxyApi.rotateTelegramProxySecret()
    if (!result) throw new Error(t('telegramProxy.rotateError'))
    toast.add({
      severity: 'success',
      summary: t('telegramProxy.rotateSuccess'),
      detail: `Operation ${result.operation_id}`,
      life: 3000,
    })
    await refreshStatus()
  } catch (error: unknown) {
    showError(error, t('telegramProxy.rotateError'))
  } finally {
    rotating.value = false
  }
}

function generateSecret() {
  const bytes = new Uint8Array(16)
  window.crypto.getRandomValues(bytes)
  form.secret = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

async function copyPublicLink() {
  const link = status.value?.links?.t_me_url ?? status.value?.links?.tg_url ?? ''
  if (!link) return
  try {
    await navigator.clipboard.writeText(link)
  } catch {
    const textArea = document.createElement('textarea')
    textArea.value = link
    textArea.style.cssText = 'position:fixed;left:-9999px;top:-9999px;opacity:0'
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  }
  toast.add({ severity: 'success', summary: t('toasts.linkCopied'), life: 2500 })
}

onMounted(loadStatusAndNodes)
</script>

<style scoped>
.telegram-proxy-page {
  display: grid;
  gap: 1rem;
}

.telegram-proxy-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1rem;
}

.telegram-proxy-grid > * {
  min-width: 0;
}

@media (max-width: 1100px) {
  .telegram-proxy-grid {
    grid-template-columns: 1fr;
  }
}
</style>
