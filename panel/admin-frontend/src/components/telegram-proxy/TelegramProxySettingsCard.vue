<template>
  <article class="settings-card telegram-proxy-settings-card">
    <div class="section-header">
      <p>{{ t('telegramProxy.settingsTitle') }}</p>
      <h3>{{ t('telegramProxy.configuration') }}</h3>
    </div>

    <div class="settings-form">
      <div class="field-row">
        <label for="telegram-proxy-enabled-switch">{{ t('telegramProxy.enabledLabel') }}</label>
        <div class="enabled-control">
          <InputSwitch id="telegram-proxy-enabled-switch" v-model="enabled" />
          <Tag :severity="enabledTagSeverity">{{ enabledTagLabel }}</Tag>
        </div>
      </div>

      <div class="form-grid">
        <div class="field">
          <label for="telegram-proxy-port">{{ t('telegramProxy.portLabel') }}</label>
          <InputNumber
            id="telegram-proxy-port"
            v-model="port"
            :min="1"
            :max="65535"
            :use-grouping="false"
          />
        </div>

        <div class="field">
          <label for="telegram-proxy-primary-node">{{ t('telegramProxy.primaryNodeLabel') }}</label>
          <Dropdown
            id="telegram-proxy-primary-node"
            v-model="primaryNodeId"
            :options="nodeOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('telegramProxy.primaryNodePlaceholder')"
            show-clear
          />
        </div>
      </div>

      <div class="field">
        <label for="telegram-proxy-public-host">{{ t('telegramProxy.publicHostLabel') }}</label>
        <InputText
          id="telegram-proxy-public-host"
          v-model.trim="publicHost"
          :placeholder="t('telegramProxy.publicHostPlaceholder')"
        />
        <small class="field-hint">{{ t('telegramProxy.publicHostHint') }}</small>
      </div>

      <div class="field">
        <div class="field-head">
          <label for="telegram-proxy-secret">{{ t('telegramProxy.secretLabel') }}</label>
          <Tag :severity="secretTagSeverity">{{ secretTagLabel }}</Tag>
        </div>

        <div class="secret-row">
          <InputText
            id="telegram-proxy-secret"
            v-model="secret"
            type="password"
            autocomplete="new-password"
            :placeholder="t('telegramProxy.secretPlaceholder')"
          />
          <Button
            :label="t('telegramProxy.generateSecret')"
            severity="secondary"
            outlined
            :disabled="busy"
            @click="emit('generateSecret')"
          />
          <Button
            :label="t('telegramProxy.rotateSecret')"
            :loading="rotating"
            :disabled="busy"
            @click="emit('rotateSecret')"
          />
        </div>

        <small class="field-hint">{{ secretHint }}</small>
      </div>

      <div class="settings-actions">
        <Button
          :label="t('telegramProxy.saveSettings')"
          :loading="saving"
          :disabled="busy"
          @click="emit('saveSettings')"
        />
        <Button
          :label="t('telegramProxy.applySettings')"
          severity="secondary"
          :loading="applying"
          :disabled="busy"
          @click="emit('applySettings')"
        />
        <Button
          :label="t('telegramProxy.disableSettings')"
          severity="danger"
          outlined
          :loading="disabling"
          :disabled="busy"
          @click="emit('disableSettings')"
        />
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import { toRefs } from 'vue'
import { useI18n } from 'vue-i18n'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import InputSwitch from 'primevue/inputswitch'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

interface NodeOption {
  label: string
  value: string
}

const enabled = defineModel<boolean>('enabled', { required: true })
const port = defineModel<number | null>('port', { required: true })
const primaryNodeId = defineModel<string | null>('primaryNodeId', { required: true })
const publicHost = defineModel<string>('publicHost', { required: true })
const secret = defineModel<string>('secret', { required: true })

const props = defineProps<{
  busy: boolean
  saving: boolean
  applying: boolean
  disabling: boolean
  rotating: boolean
  nodeOptions: NodeOption[]
  enabledTagLabel: string
  enabledTagSeverity: string
  secretTagLabel: string
  secretTagSeverity: string
  secretHint: string
}>()

const {
  busy,
  saving,
  applying,
  disabling,
  rotating,
  nodeOptions,
  enabledTagLabel,
  enabledTagSeverity,
  secretTagLabel,
  secretTagSeverity,
  secretHint,
} = toRefs(props)

const emit = defineEmits<{
  generateSecret: []
  rotateSecret: []
  saveSettings: []
  applySettings: []
  disableSettings: []
}>()

const { t } = useI18n()
</script>

<style scoped>
.telegram-proxy-settings-card {
  display: grid;
  gap: var(--app-space-4);
  min-width: 0;
}

.field-row,
.field-head,
.secret-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.enabled-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.field-row {
  justify-content: space-between;
}

.field-head {
  justify-content: space-between;
  margin-bottom: 0.35rem;
}

.secret-row {
  align-items: flex-start;
}

.field-hint {
  color: var(--app-text-muted);
}

.telegram-proxy-settings-card :deep(.p-inputtext),
.telegram-proxy-settings-card :deep(.p-dropdown),
.telegram-proxy-settings-card :deep(.p-inputnumber) {
  width: 100%;
}

@media (max-width: 1100px) {
  .secret-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
