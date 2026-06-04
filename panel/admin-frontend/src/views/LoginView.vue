<template>
  <div class="login-page">
    <section class="login-brief" :aria-label="$t('login.kicker')">
      <span class="page-kicker">{{ $t('login.kicker') }}</span>
      <h1>{{ $t('login.title') }}</h1>
      <p>{{ $t('login.description') }}</p>
      <div class="login-signals">
        <span><i class="pi pi-server" /> {{ $t('login.signalsNodes') }}</span>
        <span><i class="pi pi-users" /> {{ $t('login.signalsUsers') }}</span>
        <span><i class="pi pi-shield" /> {{ $t('login.signalsConfigs') }}</span>
      </div>
    </section>
    <div class="login-card">
      <div class="login-title">
        <span>{{ $t('login.brand') }}</span>
        <strong>{{ $t('login.subtitle') }}</strong>
      </div>
      <form class="login-form" @submit.prevent="submit">
        <div class="field">
          <label for="password">{{ $t('login.password') }}</label>
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
        <Button type="submit" :label="$t('login.submit')" :loading="loading" fluid />
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { login } from '../api/client'

const router = useRouter()
const { t } = useI18n()
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
    error.value = e instanceof Error ? e.message : t('login.error')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(20rem, 26rem);
  align-items: center;
  gap: clamp(1.5rem, 6vw, 5rem);
  background: radial-gradient(circle at 18% 20%, var(--app-accent-soft), transparent 30rem),
    linear-gradient(135deg, var(--app-bg), var(--app-bg-accent));
  padding: clamp(1.2rem, 5vw, 5rem);
}

.login-brief {
  max-width: 46rem;
}

.login-brief h1 {
  margin: 0;
  color: var(--app-text);
  font-size: clamp(3rem, 8vw, 6.5rem);
  font-weight: 950;
  line-height: 0.88;
  letter-spacing: -0.07em;
  text-transform: uppercase;
}

.login-brief p {
  max-width: 34rem;
  margin: 1.2rem 0 0;
  color: var(--app-text-muted);
  font-size: 1.05rem;
  line-height: 1.55;
}

.login-signals {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-top: 1.5rem;
}

.login-signals span {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--app-border-strong);
  border-radius: 999px;
  background: var(--app-shell);
  color: var(--app-text-muted);
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.login-card {
  background: linear-gradient(180deg, var(--app-shell), var(--app-shell-solid));
  border: 1px solid var(--app-border-strong);
  border-radius: var(--app-radius-lg);
  padding: 2rem;
  width: 100%;
  box-shadow: var(--app-shadow);
  backdrop-filter: blur(18px);
}

.login-title {
  display: grid;
  gap: 0.25rem;
  color: var(--app-text);
  margin-bottom: 1.75rem;
}

.login-title span {
  color: var(--app-accent);
  font-size: 0.72rem;
  font-weight: 900;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.login-title strong {
  font-size: 1.45rem;
  letter-spacing: -0.04em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

@media (max-width: 780px) {
  .login-page {
    grid-template-columns: 1fr;
    align-content: center;
  }

  .login-brief h1 {
    font-size: clamp(2.4rem, 14vw, 4.2rem);
  }
}
</style>
