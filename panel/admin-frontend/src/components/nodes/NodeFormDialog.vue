<template>
  <Dialog v-model:visible="visible" :header="$t('nodeForm.title')" modal :closable="!submitting">
    <form @submit.prevent="submit" class="dialog-form">
      <div class="field">
        <label>{{ $t('nodeForm.name') }}</label>
        <InputText v-model="form.name" autofocus required />
      </div>
      <div class="field">
        <label>{{ $t('nodeForm.agentUrl') }}</label>
        <InputText v-model="form.url" :placeholder="$t('nodeForm.agentUrlPlaceholder')" required />
      </div>
      <div class="field">
        <label>{{ $t('nodeForm.token') }}</label>
        <InputText v-model="form.token" required />
      </div>
      <div class="field">
        <label>{{ $t('nodeForm.publicEndpoint') }}</label>
        <InputText
          v-model="form.server_endpoint"
          :placeholder="$t('nodeForm.publicEndpointPlaceholder')"
        />
      </div>

      <div style="margin-top: 0.75rem">
        <button type="button" class="advanced-toggle" @click="showAdvanced = !showAdvanced">
          <i
            :class="showAdvanced ? 'pi pi-chevron-down' : 'pi pi-chevron-right'"
            style="font-size: 0.7rem"
          />
          {{ $t('nodeForm.obfuscationParams') }}
        </button>
        <div v-show="showAdvanced" style="margin-top: 0.5rem">
          <div style="display: flex; justify-content: flex-end; margin-bottom: 0.5rem">
            <Button
              type="button"
              :label="$t('nodeForm.randomize')"
              icon="pi pi-refresh"
              size="small"
              text
              severity="secondary"
              @click="Object.assign(form, randomObfuscation())"
            />
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem 0.75rem">
            <div class="field">
              <label>Jc</label>
              <InputNumber v-model="form.jc" :min="1" :max="128" style="width: 100%" />
            </div>
            <div class="field">
              <label>Jmin</label>
              <InputNumber v-model="form.jmin" :min="10" :max="1000" style="width: 100%" />
            </div>
            <div class="field">
              <label>Jmax</label>
              <InputNumber v-model="form.jmax" :min="10" :max="1000" style="width: 100%" />
            </div>
            <div class="field">
              <label>S1</label>
              <InputNumber v-model="form.s1" :min="15" :max="150" style="width: 100%" />
            </div>
            <div class="field">
              <label>S2</label>
              <InputNumber v-model="form.s2" :min="15" :max="150" style="width: 100%" />
            </div>
            <div></div>
            <div class="field">
              <label>S3</label>
              <InputNumber v-model="form.s3" :min="0" :max="150" style="width: 100%" />
            </div>
            <div class="field">
              <label>S4</label>
              <InputNumber v-model="form.s4" :min="0" :max="150" style="width: 100%" />
            </div>
            <div></div>
          </div>
          <div
            style="
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 0.5rem 0.75rem;
              margin-top: 0.25rem;
            "
          >
            <div class="field">
              <label>H1</label>
              <InputText v-model="form.h1" style="width: 100%; font-size: 0.85rem" />
            </div>
            <div class="field">
              <label>H2</label>
              <InputText v-model="form.h2" style="width: 100%; font-size: 0.85rem" />
            </div>
            <div class="field">
              <label>H3</label>
              <InputText v-model="form.h3" style="width: 100%; font-size: 0.85rem" />
            </div>
            <div class="field">
              <label>H4</label>
              <InputText v-model="form.h4" style="width: 100%; font-size: 0.85rem" />
            </div>
          </div>
        </div>
      </div>

      <div class="dialog-actions">
        <Button
          :label="$t('nodeForm.cancel')"
          text
          severity="secondary"
          @click="visible = false"
          :disabled="submitting"
        />
        <Button type="submit" :label="$t('nodeForm.add')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import { defaultForm, randomObfuscation } from '../../composables/useNodes'
import type { NodeCreate } from '../../api'

const visible = defineModel<boolean>('visible', { required: true })

defineProps<{
  submitting: boolean
}>()

const emit = defineEmits<{
  addNode: [formData: NodeCreate]
}>()

const showAdvanced = ref(false)
const form = reactive<NodeCreate>({ ...defaultForm })

watch(visible, (val) => {
  if (val) {
    Object.assign(form, {
      name: '',
      url: '',
      token: '',
      server_endpoint: '',
      ...randomObfuscation(),
    })
    showAdvanced.value = false
  }
})

function submit() {
  emit('addNode', { ...form })
}
</script>
