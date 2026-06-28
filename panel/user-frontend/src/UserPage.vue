<template>
  <div class="shell">
    <UserHeader :user-name="info?.user_name || null" />

    <main>
      <UserStateCard v-if="loading" state="loading" />
      <UserStateCard v-else-if="error" state="error" :is-404="error === 404" />

      <template v-else-if="info">
        <section class="hero" :class="`hero-${info.status.code}`">
          <div>
            <p class="eyebrow">{{ $t('dashboard.eyebrow') }}</p>
            <h1>{{ $t('dashboard.title', { name: info.user_name }) }}</h1>
            <p class="hero-subtitle">{{ statusText }}</p>
          </div>
          <div class="hero-status">
            <span :class="['status-pill', info.status.code]">
              {{ $t(`statuses.${info.status.code}.label`) }}
            </span>
            <span class="status-note">{{ updatedText }}</span>
          </div>
        </section>

        <TelegramProxyCard v-if="telegramProxy" :proxy="telegramProxy" />

        <UserStateCard v-if="info.blocked" state="blocked" :title="stateTitle" :text="stateBody" />
        <template v-else>
          <section class="summary-grid" :aria-label="$t('dashboard.summary')">
            <article class="summary-card primary-card">
              <span class="card-kicker">{{ $t('traffic.title') }}</span>
              <strong>{{ trafficUsed }}</strong>
              <span>{{ trafficLimitText }}</span>
              <div class="meter" :aria-label="trafficLimitText">
                <span :style="{ width: `${trafficPercent}%` }" />
              </div>
            </article>

            <article class="summary-card">
              <span class="card-kicker">{{ $t('subscription.title') }}</span>
              <strong>{{ subscriptionDate }}</strong>
              <span>{{ subscriptionText }}</span>
            </article>

            <article class="summary-card">
              <span class="card-kicker">{{ $t('connection.title') }}</span>
              <strong>{{ readyNodes }}/{{ info.nodes.length }}</strong>
              <span>{{ connectionHint }}</span>
            </article>
          </section>

          <section v-if="warningText" class="notice-card">
            <strong>{{ $t('warnings.title') }}</strong>
            <p>{{ warningText }}</p>
            <span>{{ $t('support.placeholder') }}</span>
          </section>

          <section class="guide-grid">
            <article class="guide-card platform-card">
              <div class="section-head compact-head">
                <div>
                  <h2>{{ $t('platforms.title') }}</h2>
                  <p>{{ $t('platforms.subtitle') }}</p>
                </div>
              </div>

              <div class="platform-tabs" role="tablist" :aria-label="$t('platforms.choose')">
                <button
                  v-for="platform in platforms"
                  :key="platform.id"
                  type="button"
                  role="tab"
                  :aria-selected="selectedPlatformId === platform.id"
                  :class="['platform-tab', selectedPlatformId === platform.id && 'active']"
                  @click="selectedPlatformId = platform.id"
                >
                  {{ $t(`platforms.items.${platform.id}.name`) }}
                </button>
              </div>

              <div class="platform-tabs" role="tablist" :aria-label="$t('platforms.chooseApp')">
                <button
                  v-for="app in apps"
                  :key="app"
                  type="button"
                  role="tab"
                  :aria-selected="activeTab === app"
                  :class="['platform-tab', activeTab === app && 'active']"
                  @click="activeTab = app"
                >
                  {{ $t(`platforms.apps.${app}.name`) }}
                </button>
              </div>

              <div class="platform-details">
                <div class="download-panel">
                  <div>
                    <span class="card-kicker">{{ $t('platforms.downloadApp') }}</span>
                    <h3>
                      {{ $t(`platforms.apps.${activeTab}.name`) }} ·
                      {{ $t(`platforms.items.${activePlatform.id}.name`) }}
                    </h3>
                    <p>{{ $t(`platforms.apps.${activeTab}.downloadHint`) }}</p>
                  </div>
                  <a
                    class="download-link"
                    :href="activeDownloadUrl"
                    target="_blank"
                    rel="noreferrer"
                  >
                    <DownloadIcon />
                    {{ $t('platforms.openDownload') }}
                  </a>
                </div>

                <div class="app-qr-card">
                  <img
                    :src="downloadQrUrl"
                    :alt="
                      $t('platforms.qrAlt', {
                        app: $t(`platforms.apps.${activeTab}.name`),
                        platform: $t(`platforms.items.${activePlatform.id}.name`),
                      })
                    "
                    width="168"
                    height="168"
                  />
                  <span>{{ $t('platforms.scanToDownload') }}</span>
                </div>

                <div class="instruction-panel">
                  <span class="card-kicker">{{ $t('platforms.addConfig') }}</span>
                  <ol class="platform-list">
                    <li>{{ $t('platforms.configStep1') }}</li>
                    <li>{{ $t(`platforms.apps.${activeTab}.configStep`) }}</li>
                    <li>{{ $t(`platforms.items.${activePlatform.id}.configStep`) }}</li>
                  </ol>
                </div>
              </div>
            </article>

            <article class="guide-card">
              <h2>{{ $t('help.title') }}</h2>
              <p>{{ $t('help.text') }}</p>
            </article>
          </section>

          <section class="connection-section">
            <div class="section-head">
              <div>
                <p class="eyebrow">{{ $t('dashboard.eyebrow') }}</p>
                <h2>{{ $t('connection.setupTitle') }}</h2>
              </div>
              <span class="selected-app-pill">
                {{ $t(`platforms.apps.${activeTab}.name`) }} ·
                {{ $t(`platforms.items.${activePlatform.id}.name`) }}
              </span>
            </div>

            <UserStateCard v-if="!info.nodes.length" state="empty" />
            <Transition v-else name="tab-fade" mode="out-in">
              <div :key="activeTab" class="grid">
                <ConfigCard
                  v-for="node in info.nodes"
                  :key="node.id"
                  :tab="activeTab"
                  :node="node"
                  :user-id="userId"
                  :active-qr-key="activeQrKey"
                  :qr-item="activeTab === 'vpn' ? qrMap[node.id] : defaultQrItem"
                  @toggle-qr="toggleQr"
                  @copy="copy"
                />
              </div>
            </Transition>
          </section>
        </template>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { fetchUserInfo, type TelegramProxyInfo, type UserInfo, type UserNode } from './api/userPage'
import ConfigCard from './components/ConfigCard.vue'
import UserHeader from './components/UserHeader.vue'
import TelegramProxyCard from './components/TelegramProxyCard.vue'
import UserStateCard from './components/UserStateCard.vue'
import { useVpnQrChunks } from './composables/useVpnQrChunks'
import { DownloadIcon } from './icons'
import { copyToClipboard, fmtBytes, fmtDate, fmtDateTime } from './utils/format'

type PlatformId = 'ios' | 'android' | 'macos' | 'windows' | 'linux'
type AppId = 'vpn' | 'awg'

interface PlatformOption {
  id: PlatformId
  urls: Record<AppId, string>
}

const { t, locale } = useI18n()
const route = useRoute()
const userId = route.params.userId as string

const loading = ref(true)
const error = ref<number | null>(null)
const info = ref<UserInfo | null>(null)
const activeTab = ref<'awg' | 'vpn'>('vpn')
const activeQrKey = ref<string | null>(null)
const selectedPlatformId = ref<PlatformId>('ios')
const apps: AppId[] = ['vpn', 'awg']

const platforms: PlatformOption[] = [
  {
    id: 'ios',
    urls: {
      vpn: 'https://apps.apple.com/us/app/amneziavpn/id1600529900',
      awg: 'https://apps.apple.com/us/app/amneziawg/id6478942365',
    },
  },
  {
    id: 'android',
    urls: {
      vpn: 'https://play.google.com/store/apps/details?id=org.amnezia.vpn',
      awg: 'https://play.google.com/store/apps/details?id=org.amnezia.awg',
    },
  },
  {
    id: 'macos',
    urls: {
      vpn: 'https://amnezia.org/downloads',
      awg: 'https://apps.apple.com/us/app/amneziawg/id6478942365',
    },
  },
  {
    id: 'windows',
    urls: {
      vpn: 'https://amnezia.org/downloads',
      awg: 'https://github.com/amnezia-vpn/amneziawg-windows-client/releases/latest',
    },
  },
  {
    id: 'linux',
    urls: {
      vpn: 'https://amnezia.org/downloads',
      awg: 'https://github.com/amnezia-vpn/amneziawg-go',
    },
  },
]

const { qrMap, setInfo, fetchAllVpnChunks } = useVpnQrChunks(userId)

const defaultQrItem = {
  hasChunks: false,
  hasError: false,
  chunks: [] as string[],
  idx: 0,
  chunkCount: 0,
}

const readyNodes = computed(() => info.value?.nodes.filter((node) => node.ready).length || 0)
const telegramProxy = computed<TelegramProxyInfo | null>(() => {
  const proxy = info.value?.telegram_proxy
  return proxy && proxy.enabled ? proxy : null
})
const trafficUsed = computed(() => fmtBytes(info.value?.traffic.used_bytes || 0))
const trafficPercent = computed(() => {
  const traffic = info.value?.traffic
  if (!traffic?.limit_bytes) return 100
  return Math.min(100, Math.round((traffic.used_bytes / traffic.limit_bytes) * 100))
})
const trafficLimitText = computed(() => {
  const traffic = info.value?.traffic
  if (!traffic?.limit_bytes) return t('traffic.noLimit')
  return t('traffic.ofLimit', {
    limit: fmtBytes(traffic.limit_bytes),
    percent: trafficPercent.value,
  })
})
const subscriptionDate = computed(() =>
  fmtDate(info.value?.subscription.expire_at || null, locale.value),
)
const subscriptionText = computed(() =>
  info.value?.subscription.expire_at
    ? t('subscription.expires')
    : info.value && !info.value.subscription.managed
      ? t('subscription.local')
      : t('subscription.noExpiry'),
)
const updatedText = computed(() =>
  info.value?.updated_at
    ? t('dashboard.updatedAt', { value: fmtDateTime(info.value.updated_at, locale.value) })
    : t('dashboard.updatedAt', { value: t('common.notAvailable') }),
)
const statusText = computed(() => {
  const code = info.value?.status.code || 'active'
  return t(`statuses.${code}.text`)
})
const stateTitle = computed(() => {
  const code = info.value?.status.code || 'blocked'
  return t(`statuses.${code}.label`)
})
const stateBody = computed(() => {
  const code = info.value?.status.code || 'blocked'
  return `${t(`statuses.${code}.text`)} ${t('support.placeholder')}`
})
const connectionHint = computed(() =>
  readyNodes.value > 0 ? t('connection.readyHint') : t('connection.pendingHint'),
)
const activePlatform = computed(
  () => platforms.find((platform) => platform.id === selectedPlatformId.value) || platforms[0],
)
const activeDownloadUrl = computed(() => activePlatform.value.urls[activeTab.value])
const downloadQrUrl = computed(
  () =>
    `https://api.qrserver.com/v1/create-qr-code/?size=168x168&margin=8&data=${encodeURIComponent(
      activeDownloadUrl.value,
    )}`,
)

const warningText = computed(() => {
  if (!info.value || info.value.status.code !== 'active') return ''
  const expireAt = info.value.subscription.expire_at
  if (expireAt) {
    const ms = new Date(expireAt).getTime() - Date.now()
    if (Number.isFinite(ms) && ms > 0 && ms <= 7 * 24 * 60 * 60 * 1000) {
      return t('warnings.expiring')
    }
  }
  if (info.value.traffic.limit_bytes && trafficPercent.value >= 80) {
    return t('warnings.traffic')
  }
  return ''
})

function detectPlatform(): PlatformId {
  const nav = navigator as typeof navigator & { userAgentData?: { platform?: string } }
  const platform = nav.userAgentData?.platform || nav.platform || nav.userAgent
  const value = platform.toLowerCase()
  if (value.includes('iphone') || value.includes('ipad') || value.includes('ios')) return 'ios'
  if (value.includes('android')) return 'android'
  if (value.includes('mac')) return 'macos'
  if (value.includes('win')) return 'windows'
  if (value.includes('linux')) return 'linux'
  return 'ios'
}

watch(activeTab, (tab) => {
  activeQrKey.value = null
  if (tab === 'vpn' && info.value) fetchAllVpnChunks()
})

function toggleQr(key: string) {
  activeQrKey.value = activeQrKey.value === key ? null : key
}

onMounted(async () => {
  selectedPlatformId.value = detectPlatform()
  try {
    const data = await fetchUserInfo(userId)
    info.value = data
    setInfo(data)
    fetchAllVpnChunks()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : ''
    error.value = msg === '404' ? 404 : msg ? Number(msg) || 0 : 0
  } finally {
    loading.value = false
  }
})

async function copy(node: UserNode) {
  const text = node.vpn_uri || ''
  await copyToClipboard(text)
  node.copied = true
  setTimeout(() => {
    node.copied = false
  }, 2200)
}
</script>

<style>
@import './styles/tokens.css';

*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  overflow-y: scroll;
  overflow-x: hidden;
}

body {
  font-family:
    ui-sans-serif,
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}

.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

.notice-card {
  margin-bottom: 1.5rem;
  padding: 1rem 1.2rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  display: grid;
  gap: 0.35rem;
}

main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 16px 72px;
  flex: 1;
  min-width: 0;
  width: 100%;
}

.hero {
  display: grid;
  gap: 24px;
  padding: 28px;
  margin-bottom: 20px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) + 8px);
  background: radial-gradient(
      circle at top right,
      color-mix(in srgb, var(--primary) 22%, transparent),
      transparent 42%
    ),
    var(--card);
  box-shadow: var(--shadow);
}

.hero h1 {
  max-width: 760px;
  margin-top: 6px;
  font-size: clamp(28px, 7vw, 54px);
  line-height: 0.98;
  letter-spacing: -0.055em;
}

.hero-subtitle {
  max-width: 640px;
  margin-top: 14px;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.55;
}

.eyebrow,
.card-kicker {
  color: var(--muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.hero-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  font-weight: 800;
}

.status-pill.active {
  color: var(--success);
  background: color-mix(in srgb, var(--success) 12%, transparent);
}

.status-pill.blocked,
.status-pill.expired,
.status-pill.limited {
  color: var(--danger);
  background: var(--danger-bg);
}

.status-note {
  color: var(--muted);
  font-size: 13px;
}

.summary-grid,
.guide-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  margin-bottom: 20px;
}

.summary-card,
.guide-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
  box-shadow: var(--shadow);
}

.summary-card strong {
  font-size: 30px;
  letter-spacing: -0.04em;
}

.summary-card span:not(.card-kicker),
.guide-card p {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
}

.meter {
  width: 100%;
  height: 9px;
  margin-top: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--bg-soft);
}

.meter span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--primary), var(--success));
}

.guide-card h2,
.section-head h2 {
  font-size: 20px;
  letter-spacing: -0.03em;
}

.compact-head {
  margin-bottom: 12px;
}

.platform-card {
  gap: 14px;
}

.platform-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.platform-tab {
  min-height: 38px;
  padding: 8px 13px;
  border: 1.5px solid var(--border);
  border-radius: 999px;
  background: var(--bg);
  color: var(--muted);
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.platform-tab.active {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary);
}

.platform-details {
  display: grid;
  gap: 14px;
  align-items: stretch;
}

.download-panel,
.instruction-panel,
.app-qr-card {
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) - 2px);
  background: var(--bg);
}

.download-panel,
.instruction-panel {
  padding: 16px;
}

.download-panel {
  display: grid;
  gap: 12px;
}

.download-panel h3 {
  margin: 6px 0;
  font-size: 22px;
  letter-spacing: -0.03em;
}

.download-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 800;
  text-decoration: none;
}

.download-link svg {
  width: 16px;
  height: 16px;
}

.app-qr-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 16px;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

.app-qr-card img {
  width: 168px;
  height: 168px;
  border-radius: 12px;
  background: #fff;
  padding: 8px;
}

.platform-list {
  display: grid;
  gap: 10px;
  margin-top: 8px;
  padding-left: 20px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
}

.platform-list li::marker {
  color: var(--primary);
  font-weight: 800;
}

.connection-section {
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: calc(var(--radius) + 6px);
  background: color-mix(in srgb, var(--card) 84%, transparent);
}

.section-head {
  display: grid;
  gap: 16px;
  margin-bottom: 18px;
}

.tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 8px 18px;
  border-radius: 999px;
  border: 1.5px solid var(--border);
  background: var(--card);
  color: var(--muted);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.tab-btn svg {
  width: 15px;
  height: 15px;
}

.tab-btn:hover,
.tab-btn.active {
  border-color: var(--primary);
  color: var(--primary);
}

.tab-btn.active {
  background: var(--primary-light);
}

.selected-app-pill {
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  border-radius: 999px;
  background: var(--primary-light);
  color: var(--primary);
  padding: 0 14px;
  font-size: 13px;
  font-weight: 800;
}

.tab-fade-enter-active,
.tab-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.tab-fade-enter-from,
.tab-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  align-items: start;
}

@media (min-width: 720px) {
  main {
    padding: 40px 24px 80px;
  }

  .hero {
    grid-template-columns: 1fr auto;
    align-items: end;
    padding: 40px;
  }

  .hero-status {
    justify-content: flex-end;
  }

  .summary-grid {
    grid-template-columns: 1.3fr 1fr 1fr;
  }

  .guide-grid {
    grid-template-columns: 1.2fr 0.8fr;
  }

  .platform-details {
    grid-template-columns: minmax(0, 1fr) 210px;
  }

  .instruction-panel {
    grid-column: 1 / -1;
  }

  .section-head {
    grid-template-columns: 1fr auto;
    align-items: end;
  }
}

@media (max-width: 520px) {
  .hero,
  .connection-section {
    padding: 18px;
  }
}
</style>
