<template>
  <div>
    <div class="page-header">
      <div>
        <Button
          label="К нодам"
          icon="pi pi-arrow-left"
          text
          severity="secondary"
          as="router-link"
          to="/nodes"
          style="padding-left: 0; margin-bottom: 0.35rem"
        />
        <h2>Настройки ноды</h2>
      </div>
      <Tag
        v-if="node"
        :severity="node.online ? 'success' : 'danger'"
        :value="node.online ? 'online' : 'offline'"
      />
    </div>

    <div v-if="loading" class="settings-card muted-card">Загрузка настроек…</div>
    <div v-else-if="!node" class="settings-card muted-card">Нода не найдена.</div>

    <form v-else class="settings-card settings-form" @submit.prevent="saveNode">
      <section>
        <div class="section-header">
          <h3>Основные параметры</h3>
          <p>Используются панелью для связи с агентом и клиентскими конфигами.</p>
        </div>

        <div class="form-grid">
          <div class="field">
            <label>Название</label>
            <InputText v-model="form.name" required />
          </div>
          <div class="field">
            <label>IP / URL агента</label>
            <InputText v-model="form.url" placeholder="http://1.2.3.4:8000" required />
          </div>
          <div class="field">
            <label>Токен агента</label>
            <InputText v-model="form.token" required />
          </div>
          <div class="field">
            <label>Публичный эндпоинт</label>
            <InputText v-model="form.server_endpoint" placeholder="1.2.3.4:51820" />
          </div>
        </div>
      </section>

      <section>
        <div class="section-header">
          <h3>Параметры обфускации</h3>
          <p>
            После сохранения нода будет перепровижонена, пользователям нужно перескачать конфиги.
          </p>
        </div>

        <div class="obfuscation-grid">
          <div class="field">
            <label>Jc</label>
            <InputNumber v-model="form.jc" :min="1" :max="128" style="width: 100%" />
          </div>
          <div class="field">
            <label>Jmin</label>
            <InputNumber v-model="form.jmin" :min="1" :max="1000" style="width: 100%" />
          </div>
          <div class="field">
            <label>Jmax</label>
            <InputNumber v-model="form.jmax" :min="1" :max="1000" style="width: 100%" />
          </div>
          <div class="field">
            <label>S1</label>
            <InputNumber v-model="form.s1" :min="0" :max="150" style="width: 100%" />
          </div>
          <div class="field">
            <label>S2</label>
            <InputNumber v-model="form.s2" :min="0" :max="150" style="width: 100%" />
          </div>
          <div class="field">
            <label>S3</label>
            <InputNumber v-model="form.s3" :min="0" :max="150" style="width: 100%" />
          </div>
          <div class="field">
            <label>S4</label>
            <InputNumber v-model="form.s4" :min="0" :max="150" style="width: 100%" />
          </div>
        </div>

        <div class="h-grid">
          <div class="field"><label>H1</label><InputText v-model="form.h1" /></div>
          <div class="field"><label>H2</label><InputText v-model="form.h2" /></div>
          <div class="field"><label>H3</label><InputText v-model="form.h3" /></div>
          <div class="field"><label>H4</label><InputText v-model="form.h4" /></div>
        </div>
      </section>

      <section>
        <button type="button" class="advanced-toggle" @click="showAwg2 = !showAwg2">
          <i :class="showAwg2 ? 'pi pi-chevron-down' : 'pi pi-chevron-right'" />
          AWG2: Traffic Imitation (I1–I5) / MTU
        </button>
        <div v-show="showAwg2" class="awg2-grid">
          <p class="section-note">
            Обычно синкаются с ноды автоматически. Менять вручную только если нода их не отдаёт.
          </p>
          <div class="field wide-field">
            <label>I1</label><Textarea v-model="form.i1" rows="2" />
          </div>
          <div class="field"><label>I2</label><InputText v-model="form.i2" /></div>
          <div class="field"><label>I3</label><InputText v-model="form.i3" /></div>
          <div class="field"><label>I4</label><InputText v-model="form.i4" /></div>
          <div class="field"><label>I5</label><InputText v-model="form.i5" /></div>
          <div class="field mtu-field">
            <label>MTU</label><InputText v-model="form.mtu" placeholder="1376" />
          </div>
        </div>
      </section>

      <div class="settings-actions">
        <Button label="Отмена" text severity="secondary" as="router-link" to="/nodes" />
        <Button type="submit" label="Сохранить и перепровижонить" :loading="submitting" />
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import { nodesApi } from '../api/nodes'
import type { Node, NodeUpdate } from '../api/types'

interface SettingsForm {
  name: string
  url: string
  token: string
  server_endpoint: string
  jc: number
  jmin: number
  jmax: number
  s1: number
  s2: number
  s3: number
  s4: number
  h1: string
  h2: string
  h3: string
  h4: string
  i1: string
  i2: string
  i3: string
  i4: string
  i5: string
  mtu: string
}

const route = useRoute()
const router = useRouter()
const toast = useToast()

const loading = ref(false)
const submitting = ref(false)
const showAwg2 = ref(false)
const node = ref<Node | null>(null)
const nodeId = computed(() => String(route.params.id))

const form = reactive<SettingsForm>({
  name: '',
  url: '',
  token: '',
  server_endpoint: '',
  jc: 4,
  jmin: 40,
  jmax: 70,
  s1: 0,
  s2: 0,
  s3: 0,
  s4: 0,
  h1: '1',
  h2: '2',
  h3: '3',
  h4: '4',
  i1: '',
  i2: '',
  i3: '',
  i4: '',
  i5: '',
  mtu: '',
})

function fillForm(data: Node) {
  Object.assign(form, {
    name: data.name,
    url: data.url,
    token: data.token,
    server_endpoint: data.server_endpoint ?? '',
    jc: data.jc ?? 4,
    jmin: data.jmin ?? 40,
    jmax: data.jmax ?? 70,
    s1: data.s1 ?? 0,
    s2: data.s2 ?? 0,
    s3: data.s3 ?? 0,
    s4: data.s4 ?? 0,
    h1: data.h1 ?? '1',
    h2: data.h2 ?? '2',
    h3: data.h3 ?? '3',
    h4: data.h4 ?? '4',
    i1: data.i1 ?? '',
    i2: data.i2 ?? '',
    i3: data.i3 ?? '',
    i4: data.i4 ?? '',
    i5: data.i5 ?? '',
    mtu: data.mtu ?? '',
  })
}

async function loadNode() {
  loading.value = true
  try {
    const nodes = await nodesApi.getNodes()
    node.value = nodes?.find((item) => item.id === nodeId.value) ?? null
    if (node.value) fillForm(node.value)
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e instanceof Error ? e.message : 'Ошибка',
      life: 4000,
    })
  } finally {
    loading.value = false
  }
}

async function saveNode() {
  submitting.value = true
  try {
    const payload: NodeUpdate = {
      ...form,
      name: form.name.trim(),
      url: form.url.trim(),
      token: form.token.trim(),
      server_endpoint: form.server_endpoint.trim() || null,
    }
    const updated = await nodesApi.updateNode(nodeId.value, payload)
    if (updated) node.value = updated
    toast.add({
      severity: 'success',
      summary: 'Сохранено',
      detail: 'Нода перепровижонена. Попросите пользователей перескачать конфиги.',
      life: 6000,
    })
    router.push('/nodes')
  } catch (e: unknown) {
    toast.add({
      severity: 'error',
      summary: 'Ошибка',
      detail: e instanceof Error ? e.message : 'Ошибка',
      life: 4000,
    })
  } finally {
    submitting.value = false
  }
}

onMounted(loadNode)
</script>
