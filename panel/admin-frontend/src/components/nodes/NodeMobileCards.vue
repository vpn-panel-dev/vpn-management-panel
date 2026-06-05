<template>
  <div class="mobile-card-list">
    <div v-if="loading" class="mobile-empty">{{ $t('nodeMobile.loading') }}</div>
    <div v-else-if="!nodes.length" class="mobile-empty">{{ $t('nodeMobile.empty') }}</div>
    <article v-for="node in nodes" v-else :key="node.id" class="mobile-node-card">
      <div class="mobile-card-head">
        <div>
          <div class="mobile-card-title">{{ node.name }}</div>
          <div class="mobile-card-sub">{{ node.url }}</div>
        </div>
        <Tag
          :severity="node.reachable ? 'success' : 'danger'"
          :value="node.reachable ? $t('nodeTable.reachable') : $t('nodeTable.unreachable')"
          class="status-tag"
        />
      </div>

      <div class="mobile-fields">
        <div>
          <span>{{ $t('nodeMobile.endpoint') }}</span>
          <code v-if="node.server_endpoint">{{ node.server_endpoint }}</code>
          <b v-else>—</b>
        </div>
        <div>
          <span>{{ $t('nodeMobile.metadata') }}</span>
          <div v-if="node.server_public_key" class="metadata-list">
            <code :title="node.server_public_key">{{ node.server_public_key.slice(0, 18) }}…</code>
            <span class="meta-chip">{{ $t('nodeTable.port', { port: node.listen_port }) }}</span>
            <span class="meta-chip">Jc {{ node.jc }}</span>
            <span v-if="node.mtu" class="meta-chip">MTU {{ node.mtu }}</span>
          </div>
          <Tag v-else severity="warn" :value="$t('nodeMobile.waitingSync')" class="status-tag" />
        </div>
        <div v-if="node.last_error">
          <span>{{ $t('nodeMobile.error') }}</span>
          <b class="error-text">{{ node.last_error }}</b>
        </div>
        <div>
          <span>{{ $t('nodeTable.sync') }}</span>
          <b>{{ node.sync_status }}</b>
        </div>
        <div>
          <span>{{ $t('nodeTable.provision') }}</span>
          <b>{{ node.provision_status }}</b>
        </div>
      </div>

      <div class="mobile-card-actions">
        <NodeActions
          :node-id="node.id"
          :provisioning="provisioning[node.id]"
          :mobile="true"
          @provision="$emit('provision', node)"
          @confirm-delete="$emit('confirmDelete', $event, node)"
        />
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import Tag from 'primevue/tag'
import NodeActions from './NodeActions.vue'
import type { Node } from '../../api'

defineProps<{
  nodes: Node[]
  loading: boolean
  provisioning: Record<string, boolean>
}>()

defineEmits<{
  provision: [node: Node]
  confirmDelete: [event: Event, node: Node]
}>()
</script>
