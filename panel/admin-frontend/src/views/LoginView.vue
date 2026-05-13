<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-title">AmneziaWG Panel</div>
      <form class="login-form" @submit.prevent="submit">
        <div class="field">
          <label for="password">Пароль</label>
          <Password
            id="password"
            v-model="password"
            :feedback="false"
            toggleMask
            autofocus
            fluid
            @keydown.enter="submit"
          />
        </div>
        <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
        <Button type="submit" label="Войти" :loading="loading" fluid />
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { login } from '../api/client'

const router = useRouter()
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  if (!password.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await login(password.value)
    localStorage.setItem('token', data.token)
    router.push('/nodes')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Ошибка входа'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(
      circle at 25% 20%,
      color-mix(in srgb, var(--p-primary-300) 32%, transparent),
      transparent 30rem
    ),
    linear-gradient(135deg, var(--app-bg), var(--app-bg-accent));
  padding: 1.5rem;
}

.login-card {
  background: var(--app-shell);
  border: 1px solid var(--app-border);
  border-radius: 22px;
  padding: 2.5rem 2rem;
  width: 100%;
  max-width: 22rem;
  box-shadow: var(--app-shadow);
  backdrop-filter: blur(18px);
}

.login-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--app-text);
  margin-bottom: 1.75rem;
  text-align: center;
  letter-spacing: 0.02em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
