<template>
  <template v-if="isLoginPage">
    <RouterView />
  </template>
  <template v-else>
    <div class="layout">
      <header class="topbar">
        <div class="brand-block">
          <span class="brand-mark">AWG</span>
          <div>
            <span class="brand">{{ $t('app.brand') }}</span>
            <span class="brand-subtitle">{{ $t('app.subtitle') }}</span>
          </div>
        </div>
        <div class="topbar-actions">
          <Select
            :modelValue="currentLocale"
            :options="langOptions"
            optionLabel="name"
            optionValue="code"
            size="small"
            class="lang-select"
            :aria-label="$t('navigation.language')"
            @update:modelValue="switchLocale"
          />
          <Button
            :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
            text
            rounded
            size="small"
            v-tooltip.bottom="isDark ? $t('navigation.themeLight') : $t('navigation.themeDark')"
            class="theme-btn"
            @click="toggleTheme"
          />
          <Button
            icon="pi pi-sign-out"
            text
            rounded
            size="small"
            v-tooltip.bottom="$t('navigation.logout')"
            class="logout-btn"
            @click="logout"
          />
        </div>
        <nav :aria-label="$t('navigation.menu')">
          <RouterLink to="/nodes"
            ><i class="pi pi-server" /> {{ $t('navigation.nodes') }}</RouterLink
          >
          <RouterLink to="/users"
            ><i class="pi pi-users" /> {{ $t('navigation.users') }}</RouterLink
          >
          <RouterLink to="/integrations/remnawave"
            ><i class="pi pi-sync" /> {{ $t('navigation.remnawave') }}</RouterLink
          >
          <RouterLink to="/integrations/telegram-proxy"
            ><i class="pi pi-send" /> {{ $t('navigation.telegramProxy') }}</RouterLink
          >
        </nav>
      </header>
      <main class="content">
        <RouterView />
      </main>
    </div>
  </template>
  <Toast position="top-right" />
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import Toast from 'primevue/toast'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { useI18n } from 'vue-i18n'
import { i18n, setLocale } from './i18n'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const isLoginPage = computed(() => route.path === '/login')

const isDark = ref(true)

const currentLocale = computed(() => i18n.global.locale.value)

const langOptions = [
  { code: 'ru', name: t('common.languages.ru') },
  { code: 'en', name: t('common.languages.en') },
  { code: 'zh', name: t('common.languages.zh') },
]

const THEME_COOKIE = 'amnezia-theme'

function saveThemePreference(theme: 'dark' | 'light') {
  const expires = new Date()
  expires.setFullYear(expires.getFullYear() + 1)
  document.cookie = `${THEME_COOKIE}=${theme}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`
}

onMounted(() => {
  const html = document.documentElement
  isDark.value = html.classList.contains('app-dark')
})

function toggleTheme() {
  const html = document.documentElement
  isDark.value = !isDark.value
  if (isDark.value) {
    html.classList.add('app-dark')
    saveThemePreference('dark')
  } else {
    html.classList.remove('app-dark')
    saveThemePreference('light')
  }
}

function switchLocale(locale: string) {
  setLocale(locale)
}

function logout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>

<style>
@import './styles/tokens.css';
@import './styles/shared.css';

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: 'Avenir Next Condensed', 'DIN Alternate', 'Trebuchet MS', sans-serif;
  background: var(--app-bg);
  color: var(--app-text);
  font-variant-numeric: tabular-nums;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background-image: linear-gradient(var(--app-gridline) 1px, transparent 1px),
    linear-gradient(90deg, var(--app-gridline) 1px, transparent 1px),
    radial-gradient(
      circle at 18% 14%,
      color-mix(in srgb, var(--app-accent) 18%, transparent),
      transparent 30rem
    ),
    radial-gradient(
      circle at 90% 10%,
      color-mix(in srgb, var(--app-cyan) 16%, transparent),
      transparent 26rem
    ),
    linear-gradient(135deg, var(--app-bg), var(--app-bg-accent));
  background-size:
    42px 42px,
    42px 42px,
    auto,
    auto,
    auto;
}

.layout {
  display: grid;
  grid-template-columns: 17rem minmax(0, 1fr);
  min-height: 100vh;
}

.topbar {
  display: flex;
  position: sticky;
  top: 0;
  z-index: 10;
  flex-direction: column;
  align-items: center;
  gap: var(--app-space-5);
  min-height: 100vh;
  padding: var(--app-space-5) var(--app-space-4);
  background: linear-gradient(
    180deg,
    var(--app-shell),
    color-mix(in srgb, var(--app-shell-solid) 82%, transparent)
  );
  border-right: 1px solid var(--app-border-strong);
  backdrop-filter: blur(18px) saturate(130%);
  box-shadow: 1px 0 0 rgba(255, 255, 255, 0.04);
}

.brand-block {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.75rem;
  width: 100%;
  align-items: center;
}

.brand-mark {
  display: grid;
  width: 3rem;
  height: 3rem;
  place-items: center;
  border: 1px solid var(--app-border-strong);
  border-radius: 14px;
  background: linear-gradient(
    135deg,
    var(--app-accent),
    color-mix(in srgb, var(--app-cyan) 70%, #000)
  );
  color: #10120f;
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  box-shadow: 0 18px 36px color-mix(in srgb, var(--app-accent) 20%, transparent);
}

.brand {
  display: block;
  font-weight: 900;
  font-size: 1.05rem;
  color: var(--app-text);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.brand-subtitle {
  display: block;
  margin-top: 0.15rem;
  color: var(--app-text-soft);
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

nav {
  display: grid;
  gap: var(--app-space-2);
  width: 100%;
}

nav a {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  text-decoration: none;
  color: var(--app-text-muted);
  padding: 0.85rem 0.95rem;
  border: 1px solid transparent;
  border-radius: var(--app-radius-md);
  font-size: 0.92rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  transition:
    background 0.15s,
    color 0.15s,
    border-color 0.15s,
    transform 0.15s;
}

nav a:hover {
  background: var(--app-hover);
  color: var(--app-text);
  border-color: var(--app-border);
  transform: translateX(2px);
}

nav a.router-link-active {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--app-accent) 18%, transparent),
    color-mix(in srgb, var(--app-cyan) 13%, transparent)
  );
  color: var(--app-text);
  border-color: color-mix(in srgb, var(--app-accent) 42%, var(--app-border));
  box-shadow:
    inset 3px 0 0 var(--app-accent),
    0 10px 26px rgba(0, 0, 0, 0.13);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  width: 100%;
}

.lang-select {
  flex: 1 1 auto;
  min-width: 0;
}

.lang-select .p-select-label {
  font-size: 0.78rem;
  font-weight: 800;
  padding: 0.45rem 0.65rem;
}

.lang-select .p-select-dropdown {
  width: 2rem;
}

.theme-btn {
  color: var(--app-text-muted) !important;
}

.theme-btn:hover {
  color: var(--app-text) !important;
}

.logout-btn {
  color: var(--app-text-muted) !important;
}

.logout-btn:hover {
  color: var(--app-text) !important;
}

.content {
  min-width: 0;
  padding: clamp(1rem, 2.4vw, 2.5rem);
  max-width: 1560px;
  width: 100%;
  margin: 0 auto;
}

.p-datatable {
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-lg);
  overflow: hidden;
  background: var(--app-shell-solid);
  box-shadow: var(--app-shadow);
}

.p-datatable .p-datatable-header,
.p-datatable .p-datatable-thead > tr > th,
.p-datatable .p-datatable-tbody > tr,
.p-datatable .p-datatable-tbody > tr > td {
  background: transparent;
  color: var(--app-text);
}

.p-datatable .p-datatable-thead > tr > th {
  background: color-mix(in srgb, var(--app-shell-solid) 78%, var(--app-accent) 10%);
  border-color: var(--app-border);
  color: var(--app-text-muted);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.p-datatable .p-datatable-tbody > tr > td {
  border-color: var(--app-border);
}

.p-datatable .p-datatable-tbody > tr:hover {
  background: var(--app-hover);
}

.p-datatable .p-datatable-row-expansion > td {
  background: color-mix(in srgb, var(--app-shell-solid) 82%, var(--app-cyan) 8%);
}

.p-dialog,
.p-popover,
.p-menu {
  border: 1px solid var(--app-border-strong);
  box-shadow: var(--app-shadow);
}

.p-button {
  font-weight: 800;
  letter-spacing: 0.01em;
}

.p-tag {
  font-weight: 900;
  letter-spacing: 0.045em;
  text-transform: uppercase;
}

.p-inputtext,
.p-inputnumber-input,
.p-password-input,
.p-textarea {
  background: color-mix(in srgb, var(--app-surface-raised) 92%, transparent);
  border-color: var(--app-border-strong);
  color: var(--app-text);
}

@media (max-width: 760px) {
  .layout {
    display: block;
  }

  .topbar {
    position: sticky;
    min-height: 4rem;
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.7rem 1rem;
    padding: 0.75rem 1rem;
    border-right: none;
    border-bottom: 1px solid var(--app-border-strong);
  }

  .brand-block {
    flex: 1 1 auto;
    min-width: 12rem;
  }

  nav {
    order: 3;
    width: 100%;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    overflow: visible;
    padding-bottom: 0.1rem;
  }

  nav a {
    justify-content: center;
    gap: 0.35rem;
    padding: 0.55rem 0.35rem;
    font-size: 0.78rem;
    white-space: nowrap;
  }

  .topbar-actions {
    width: auto;
    margin-left: 0;
    margin-top: 0;
    padding-top: 0;
    border-top: 0;
  }

  .content {
    padding: 1rem 0.75rem 2rem;
  }

  .p-datatable {
    border-radius: 16px;
    overflow-x: auto;
  }

  .p-datatable-table {
    min-width: 760px;
  }

  .lang-select {
    max-width: 8rem;
  }
}
</style>
