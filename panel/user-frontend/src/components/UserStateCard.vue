<template>
  <!-- Loading skeleton -->
  <div v-if="state === 'loading'" class="centered">
    <div class="skeleton-loader">
      <div class="skeleton-header" />
      <div class="skeleton-tabs">
        <div class="skeleton-tab" />
        <div class="skeleton-tab" />
      </div>
      <div class="skeleton-grid">
        <div class="skeleton-card" v-for="i in 2" :key="i">
          <div class="skeleton-card-head" />
          <div class="skeleton-card-body" />
          <div class="skeleton-card-actions" />
        </div>
      </div>
    </div>
  </div>

  <!-- Error -->
  <div v-else-if="state === 'error'" class="centered">
    <div class="state-card">
      <div class="state-icon error-icon">
        <ErrorCircleIcon />
      </div>
      <div class="state-title">
        {{ is404 ? 'Страница не найдена' : 'Ошибка загрузки' }}
      </div>
      <div class="state-sub">
        {{ is404 ? 'Проверьте ссылку.' : 'Попробуйте обновить страницу.' }}
      </div>
    </div>
  </div>

  <!-- Blocked -->
  <div v-else-if="state === 'blocked'" class="centered">
    <div class="state-card">
      <div class="state-icon error-icon">
        <ErrorCircleIcon />
      </div>
      <div class="state-title">Доступ закрыт</div>
      <div class="state-sub">Аккаунт деактивирован. Обратитесь к администратору.</div>
    </div>
  </div>

  <!-- Empty (no nodes) -->
  <div v-else-if="state === 'empty'" class="centered" style="padding-top: 60px">
    <div class="state-card">
      <div class="state-icon">
        <InfoCircleIcon />
      </div>
      <div class="state-title">Серверы не настроены</div>
      <div class="state-sub">Обратитесь к администратору.</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ErrorCircleIcon, InfoCircleIcon } from '../icons'

defineProps<{
  state: 'loading' | 'error' | 'blocked' | 'empty'
  is404?: boolean
}>()
</script>

<style scoped>
.centered {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}
.skeleton-loader {
  width: 100%;
  max-width: 800px;
}
.skeleton-header {
  height: 36px;
  width: 60%;
  background: var(--skeleton);
  border-radius: 8px;
  margin-bottom: 24px;
  animation: skeleton-pulse 1.5s infinite;
}
.skeleton-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 28px;
}
.skeleton-tab {
  height: 40px;
  width: 140px;
  background: var(--skeleton);
  border-radius: 8px;
  animation: skeleton-pulse 1.5s infinite;
}
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}
.skeleton-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  height: 420px;
}
.skeleton-card-head {
  height: 48px;
  background: var(--skeleton);
  animation: skeleton-pulse 1.5s infinite;
}
.skeleton-card-body {
  height: 280px;
  margin: 20px auto;
  width: 80%;
  background: var(--skeleton);
  border-radius: 10px;
  animation: skeleton-pulse 1.5s infinite;
}
.skeleton-card-actions {
  height: 44px;
  margin: 0 18px;
  background: var(--skeleton);
  border-radius: 8px;
  animation: skeleton-pulse 1.5s infinite;
}
@keyframes skeleton-pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
  100% {
    opacity: 1;
  }
}
.state-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 48px 40px;
  text-align: center;
  max-width: 380px;
  width: 100%;
  box-shadow: var(--shadow);
}
.state-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--bg);
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.state-icon svg {
  width: 26px;
  height: 26px;
  color: var(--muted);
}
.error-icon {
  background: var(--danger-bg);
}
.error-icon svg {
  color: var(--danger);
}
.state-title {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 6px;
}
.state-sub {
  font-size: 14px;
  color: var(--muted);
}
</style>
