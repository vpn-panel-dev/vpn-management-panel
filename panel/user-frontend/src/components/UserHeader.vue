<template>
  <header>
    <div class="header-inner">
      <div class="logo">
        <ShieldIcon />
      </div>
      <span class="brand">{{ $t('app.brand') }}</span>
      <div class="spacer" />
      <div class="settings" :aria-label="$t('settings.title')">
        <label>
          <span>{{ $t('settings.language') }}</span>
          <select v-model="currentLocale" @change="changeLocale">
            <option value="ru">Русский</option>
            <option value="en">English</option>
            <option value="zh">简体中文</option>
          </select>
        </label>
        <label>
          <span>{{ $t('settings.theme') }}</span>
          <select v-model="theme" @change="applyTheme">
            <option value="system">{{ $t('settings.themeSystem') }}</option>
            <option value="light">{{ $t('settings.themeLight') }}</option>
            <option value="dark">{{ $t('settings.themeDark') }}</option>
          </select>
        </label>
      </div>
      <div v-if="userName" class="user-badge">
        <div class="avatar">{{ userName[0].toUpperCase() }}</div>
        <span>{{ userName }}</span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ShieldIcon } from '../icons'
import { setLocale } from '../i18n'

defineProps<{ userName: string | null }>()

type Theme = 'system' | 'light' | 'dark'

const { locale } = useI18n()
const currentLocale = ref(locale.value)
const theme = ref<Theme>('system')

function applyTheme() {
  localStorage.setItem('amnezia-user-theme', theme.value)
  if (theme.value === 'system') {
    document.documentElement.removeAttribute('data-theme')
    return
  }
  document.documentElement.dataset.theme = theme.value
}

function changeLocale() {
  setLocale(currentLocale.value)
}

onMounted(() => {
  const savedTheme = localStorage.getItem('amnezia-user-theme')
  if (savedTheme === 'light' || savedTheme === 'dark' || savedTheme === 'system') {
    theme.value = savedTheme
  }
  applyTheme()
})
</script>

<style scoped>
header {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-inner {
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px;
  height: 60px;
  display: flex;
  align-items: center;
  gap: 12px;
}
.logo {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--primary) 0%, #7c3aed 100%);
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.3);
}
.logo svg {
  width: 18px;
  height: 18px;
}
.brand {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.spacer {
  flex: 1;
}
.settings {
  display: flex;
  align-items: center;
  gap: 8px;
}
.settings label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}
.settings select {
  height: 34px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--bg);
  color: var(--text);
  padding: 0 28px 0 10px;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
}
.user-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 4px 12px 4px 4px;
  font-size: 13px;
  font-weight: 500;
}
.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--primary) 0%, #7c3aed 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}
@media (max-width: 600px) {
  .header-inner {
    height: auto;
    min-height: 60px;
    flex-wrap: wrap;
    padding: 10px 16px;
  }
  .settings {
    order: 3;
    width: 100%;
  }
  .settings label {
    flex: 1;
  }
  .settings select {
    width: 100%;
  }
  .user-badge {
    display: none;
  }
}
</style>
