<template>
  <article class="proxy-card">
    <div class="proxy-head">
      <div>
        <p class="card-kicker">{{ t('telegramProxy.kicker') }}</p>
        <h2>{{ t('telegramProxy.title') }}</h2>
        <p class="proxy-text">
          {{ t('telegramProxy.subtitle', { node: proxy.primary_node_name }) }}
        </p>
      </div>

      <div class="proxy-state">
        <span class="proxy-badge">{{ t('telegramProxy.enabled') }}</span>
        <span class="proxy-status">{{
          t('telegramProxy.proxyStatus', { status: proxy.status })
        }}</span>
      </div>
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
  padding: 20px;
  margin-bottom: 20px;
  display: grid;
  gap: 20px;
}

.proxy-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.card-kicker {
  margin: 0 0 4px;
}

h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  letter-spacing: -0.03em;
}

.proxy-text {
  max-width: 48ch;
  margin: 10px 0 0;
  color: var(--muted);
  line-height: 1.5;
}

.proxy-state {
  display: grid;
  justify-items: end;
  gap: 8px;
  text-align: right;
}

.proxy-badge {
  border-radius: 999px;
  background: var(--success-bg);
  color: var(--success);
  font-size: 12px;
  font-weight: 700;
  padding: 6px 10px;
}

.proxy-status {
  color: var(--muted);
  font-size: 13px;
  line-height: 1.35;
}

.proxy-actions {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) auto;
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
  min-width: 0;
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

  .proxy-state {
    justify-items: start;
    text-align: left;
  }

  .proxy-actions {
    grid-template-columns: 1fr;
  }

  .proxy-primary,
  .proxy-secondary,
  .proxy-copy {
    width: 100%;
  }
}
</style>
