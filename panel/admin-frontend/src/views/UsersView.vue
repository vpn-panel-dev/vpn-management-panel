<template>
  <div>
    <div class="page-header">
      <h2>Пользователи</h2>
      <div class="user-toolbar">
        <InputText
          v-model="newName"
          placeholder="Имя пользователя"
          @keyup.enter="addUser"
          size="small"
        />
        <Button
          label="Добавить"
          icon="pi pi-plus"
          size="small"
          @click="addUser"
          :loading="addingUser"
        />
      </div>
    </div>

    <UserTable
      :users="users"
      :loading="loading"
      :ready-nodes="readyNodes"
      @block="block"
      @unblock="unblock"
      @confirm-delete="confirmDelete"
      @show-traffic="showTraffic"
      @copy-user-link="copyUserLink"
      @download-config="downloadConfig"
      @download-config-zip="downloadConfigZip"
      @show-qr="showQr"
    />

    <UserMobileCards
      :users="users"
      :loading="loading"
      :ready-nodes="readyNodes"
      @block="block"
      @unblock="unblock"
      @confirm-delete="confirmDelete"
      @show-traffic="showTraffic"
      @copy-user-link="copyUserLink"
      @download-config="downloadConfig"
      @download-config-zip="downloadConfigZip"
      @show-qr="showQr"
    />

    <UserQrDialog
      :visible="qrDialog.visible"
      @update:visible="qrDialog.visible = $event"
      :title="qrDialog.title"
      :src-wg="qrDialog.srcWg"
      :src-amnezia="qrDialog.srcAmnezia"
      :current-tab="qrDialog.tab"
      @update:tab="qrDialog.tab = $event"
    />

    <ConfirmPopup />

    <UserTrafficDialog
      :visible="trafficDialog.visible"
      @update:visible="trafficDialog.visible = $event"
      :title="trafficDialog.title"
      :loading="trafficDialog.loading"
      :data="trafficDialog.data"
      :max-val="trafficDialog.maxVal"
      :user="trafficDialog.user"
      :local-totals="trafficDialog.localTotals"
      :local-daily="trafficDialog.localDaily"
      :local-nodes="trafficDialog.localNodes"
      :local-nodes-daily="trafficDialog.localNodesDaily"
    />
  </div>
</template>

<script setup lang="ts">
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import ConfirmPopup from 'primevue/confirmpopup'
import UserTable from '../components/users/UserTable.vue'
import UserMobileCards from '../components/users/UserMobileCards.vue'
import UserQrDialog from '../components/users/UserQrDialog.vue'
import UserTrafficDialog from '../components/users/UserTrafficDialog.vue'
import { useUsers } from '../composables/useUsers'
import { useDownloads } from '../composables/useDownloads'

const { users, loading, newName, addingUser, readyNodes, addUser, block, unblock, confirmDelete } =
  useUsers()

const {
  qrDialog,
  trafficDialog,
  showQr,
  downloadConfig,
  downloadConfigZip,
  copyUserLink,
  showTraffic,
} = useDownloads()
</script>

<style scoped>
.user-toolbar {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 760px) {
  .user-toolbar {
    width: 100%;
    justify-content: stretch;
  }

  .user-toolbar :deep(.p-inputtext),
  .user-toolbar :deep(.p-button) {
    flex: 1 1 100%;
  }
}
</style>
