<template>
  <div class="shell">
    <UserHeader :user-name="info && !info.blocked ? info.user_name : null" />

    <main>
      <UserStateCard v-if="loading" state="loading" />
      <UserStateCard v-else-if="error" state="error" :is-404="error === 404" />
      <UserStateCard v-else-if="info?.blocked" state="blocked" />

      <template v-else-if="info">
        <div class="page-head">
          <div class="page-title">Настройка подключения</div>
          <div class="page-sub">
            Выберите приложение, отсканируйте QR-код или скачайте конфигурацию.
          </div>
        </div>

        <UserStateCard v-if="!info.nodes.length" state="empty" />

        <template v-else>
          <div class="tabs">
            <button
              :class="['tab-btn', activeTab === 'awg' && 'active']"
              @click="activeTab = 'awg'"
            >
              <MonitorIcon />
              AmneziaWG
            </button>
            <button
              :class="['tab-btn', activeTab === 'vpn' && 'active']"
              @click="activeTab = 'vpn'"
            >
              <ShieldTabIcon />
              AmneziaVPN
            </button>
          </div>

          <div class="tab-panels">
            <Transition name="tab-fade" mode="out-in">
              <div v-if="activeTab === 'awg'" key="awg" class="grid">
                <ConfigCard
                  v-for="node in info.nodes"
                  :key="node.id"
                  tab="awg"
                  :node="node"
                  :user-id="userId"
                  :active-qr-key="activeQrKey"
                  :qr-item="defaultQrItem"
                  @toggle-qr="toggleQr"
                />
              </div>
              <div v-else key="vpn" class="grid">
                <ConfigCard
                  v-for="node in info.nodes"
                  :key="node.id"
                  tab="vpn"
                  :node="node"
                  :user-id="userId"
                  :active-qr-key="activeQrKey"
                  :qr-item="qrMap[node.id]"
                  @toggle-qr="toggleQr"
                  @copy="copy"
                />
              </div>
            </Transition>
          </div>
        </template>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { MonitorIcon, ShieldTabIcon } from './icons'
import { fetchUserInfo, type UserInfo, type UserNode } from './api/userPage'
import { useVpnQrChunks } from './composables/useVpnQrChunks'
import { copyToClipboard } from './utils/format'
import UserHeader from './components/UserHeader.vue'
import UserStateCard from './components/UserStateCard.vue'
import ConfigCard from './components/ConfigCard.vue'

const route = useRoute()
const userId = route.params.userId as string

const loading = ref(true)
const error = ref<number | null>(null)
const info = ref<UserInfo | null>(null)
const activeTab = ref<'awg' | 'vpn'>('awg')
const activeQrKey = ref<string | null>(null)

const { qrMap, setInfo, fetchAllVpnChunks } = useVpnQrChunks(userId)

const defaultQrItem = {
  hasChunks: false,
  hasError: false,
  chunks: [] as string[],
  idx: 0,
  chunkCount: 0,
}

watch(activeTab, (tab) => {
  activeQrKey.value = null
  if (tab === 'vpn' && info.value) fetchAllVpnChunks()
})

function toggleQr(key: string) {
  activeQrKey.value = activeQrKey.value === key ? null : key
}

onMounted(async () => {
  try {
    const data = await fetchUserInfo(userId)
    info.value = data
    setInfo(data)
    if (activeTab.value === 'vpn') fetchAllVpnChunks()
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

main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 40px 24px 80px;
  flex: 1;
  min-width: 0;
  width: 100%;
}

.page-head {
  margin-bottom: 32px;
}
.page-title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
  margin-bottom: 4px;
}
.page-sub {
  font-size: 15px;
  color: var(--muted);
}

.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 28px;
}
.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  border-radius: 8px;
  border: 1.5px solid var(--border);
  background: var(--card);
  color: var(--muted);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn svg {
  width: 15px;
  height: 15px;
}
.tab-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}
.tab-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
}

.tab-panels {
  position: relative;
}
.tab-fade-enter-active,
.tab-fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}
.tab-fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.tab-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  align-items: start;
}

@media (max-width: 600px) {
  main {
    padding: 28px 16px 60px;
  }
  .page-title {
    font-size: 22px;
  }
  .tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
  .tab-btn {
    justify-content: center;
    padding: 9px 10px;
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
