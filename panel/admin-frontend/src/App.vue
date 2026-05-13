<template>
  <template v-if="isLoginPage">
    <RouterView />
  </template>
  <template v-else>
    <div class="layout">
      <header class="topbar">
        <span class="brand">AmneziaWG Panel</span>
        <nav>
          <RouterLink to="/nodes">Ноды</RouterLink>
          <RouterLink to="/users">Пользователи</RouterLink>
          <RouterLink to="/integrations/remnawave">Remnawave</RouterLink>
        </nav>
        <div class="topbar-actions">
          <Button
            :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
            text
            rounded
            size="small"
            v-tooltip.bottom="isDark ? 'Светлая тема' : 'Тёмная тема'"
            class="theme-btn"
            @click="toggleTheme"
          />
          <Button
            icon="pi pi-sign-out"
            text
            rounded
            size="small"
            v-tooltip.bottom="'Выйти'"
            class="logout-btn"
            @click="logout"
          />
        </div>
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

const route = useRoute()
const router = useRouter()

const isLoginPage = computed(() => route.path === '/login')

const isDark = ref(true)

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
  font-family:
    ui-sans-serif,
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
  background: var(--app-bg);
  color: var(--app-text);
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background: radial-gradient(
      circle at 14% 10%,
      color-mix(in srgb, var(--p-primary-300) 34%, transparent),
      transparent 34rem
    ),
    radial-gradient(
      circle at 82% 6%,
      color-mix(in srgb, var(--p-cyan-300) 24%, transparent),
      transparent 28rem
    ),
    linear-gradient(135deg, var(--app-bg), var(--app-bg-accent));
}

.layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 2rem;
  padding: 0 1.5rem;
  height: 4rem;
  background: var(--app-shell);
  border-bottom: 1px solid var(--app-border);
  backdrop-filter: blur(18px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.35);
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.brand {
  font-weight: 700;
  font-size: 1rem;
  color: var(--app-text);
  letter-spacing: 0.02em;
}

nav {
  display: flex;
  gap: 0.25rem;
}

nav a {
  text-decoration: none;
  color: var(--app-text-muted);
  padding: 0.35rem 0.85rem;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: 600;
  transition:
    background 0.15s,
    color 0.15s;
}

nav a:hover {
  background: var(--app-hover);
  color: var(--app-text);
}

nav a.router-link-active {
  background: linear-gradient(135deg, var(--p-primary-500), var(--p-primary-600));
  color: #fff;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
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
  flex: 1;
  padding: 2rem 1.5rem;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}

.p-datatable {
  border: 1px solid var(--app-border);
  border-radius: 18px;
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
  background: color-mix(in srgb, var(--app-shell-solid) 84%, var(--p-primary-100));
  border-color: var(--app-border);
  color: var(--app-text-muted);
  font-size: 0.76rem;
  font-weight: 750;
  letter-spacing: 0.045em;
  text-transform: uppercase;
}

.p-datatable .p-datatable-tbody > tr > td {
  border-color: var(--app-border);
}

.p-datatable .p-datatable-tbody > tr:hover {
  background: var(--app-hover);
}

.p-datatable .p-datatable-row-expansion > td {
  background: color-mix(in srgb, var(--app-shell-solid) 78%, var(--p-primary-50));
}

.p-dialog,
.p-popover,
.p-menu {
  border: 1px solid var(--app-border-strong);
  box-shadow: var(--app-shadow);
}

@media (max-width: 760px) {
  .topbar {
    height: auto;
    min-height: 4rem;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 0.7rem 1rem;
    padding: 0.75rem 1rem;
  }

  .brand {
    flex: 1 1 auto;
    min-width: 12rem;
    line-height: 2rem;
  }

  nav {
    order: 3;
    width: 100%;
    overflow-x: auto;
    padding-bottom: 0.1rem;
  }

  nav a {
    white-space: nowrap;
  }

  .topbar-actions {
    margin-left: 0;
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
}
</style>
