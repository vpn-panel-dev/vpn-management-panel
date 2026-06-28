<template>
  <article class="proxy-card">
    <div class="proxy-head">
      <div>
        <p class="card-kicker">{{ t('telegramProxy.kicker') }}</p>
        <h2>{{ t('telegramProxy.title') }}</h2>
      </div>
      <span class="proxy-badge">{{ t('telegramProxy.enabled') }}</span>
    </div>

    <p class="proxy-text">
      {{ t('telegramProxy.subtitle', { node: proxy.primary_node_name }) }}
    </p>

    <div class="proxy-meta">
      <span>{{ t('telegramProxy.primaryNode', { node: proxy.primary_node_name }) }}</span>
      <span>{{ t('telegramProxy.proxyStatus', { status: proxy.status }) }}</span>
    </div>

    <div class="proxy-actions">
      <a class="proxy-primary" :href="proxy.tg_url" target="_blank" rel="noreferrer">
        {{ t('telegramProxy.openTelegram') }}
      </a>
      <a class="proxy-secondary" :href="proxy.https_url" target="_blank" rel="noreferrer">
        {{ t('telegramProxy.openFallback') }}
      </a>
      <button type="button" class="proxy-copy" @click="copyHttpsUrl">
        {{ copied ? t('telegramProxy.copied') : t('telegramProxy.copyFallback') }}
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TelegramProxyInfo } from '../api/userPage'
import { copyToClipboard } from '../utils/format'

const { t } = useI18n()
const props = defineProps<{ proxy: TelegramProxyInfo }>()

const copied = ref(false)

async function copyHttpsUrl() {
  await copyToClipboard(props.proxy.https_url)
  copied.value = true
  window.setTimeout(() => {
    copied.value = false
  }, 2200)
}
</script>

<style scoped>
.proxy-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 24px;
  display: grid;
  gap: 16px;
}

.proxy-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.card-kicker {
  margin: 0 0 4px;
}

h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
}

.proxy-badge {
  border-radius: 999px;
  background: var(--success-bg);
  color: var(--success);
  font-size: 12px;
  font-weight: 700;
  padding: 6px 10px;
  white-space: nowrap;
}

.proxy-text {
  margin: 0;
  color: var(--muted);
}

.proxy-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: var(--muted);
  font-size: 13px;
}

.proxy-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.proxy-primary,
.proxy-secondary,
.proxy-copy {
  border-radius: 999px;
  border: 1px solid var(--border);
  min-height: 42px;
  padding: 0 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font: inherit;
  font-weight: 700;
  text-decoration: none;
}

.proxy-primary {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.proxy-secondary,
.proxy-copy {
  background: var(--bg);
  color: var(--text);
}

.proxy-copy {
  cursor: pointer;
}

@media (max-width: 640px) {
  .proxy-head {
    flex-direction: column;
  }

  .proxy-actions {
    flex-direction: column;
  }

  .proxy-primary,
  .proxy-secondary,
  .proxy-copy {
    width: 100%;
  }
}
</style>
