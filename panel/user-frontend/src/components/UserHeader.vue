<template>
  <header>
    <div class="header-inner">
      <div class="logo">
        <ShieldIcon />
      </div>
      <span class="brand">{{ $t('app.brand') }}</span>
      <div class="spacer" />
      <div v-if="userName" class="user-badge">
        <div class="avatar">{{ userName[0].toUpperCase() }}</div>
        <span>{{ userName }}</span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ShieldIcon } from '../icons'

defineProps<{ userName: string | null }>()
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
  .user-badge {
    display: none;
  }
}
</style>
