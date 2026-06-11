import type { Node, RemnawaveUserBrief } from '../api/types'
import { i18n } from '../i18n/index.ts'
import { fmtBytes, fmtDate } from './format'

const pendingOperationStatuses = new Set(['running', 'queued', 'pending'])
const failedOperationStatuses = new Set(['failed', 'failed_by_timeout', 'enqueue_failed'])

/**
 * Map a peer status string to a PrimeVue Tag severity.
 *
 * @example peerSeverity('active') → 'success'
 */
export function peerSeverity(status: string, isBlocked = false): string {
  if (isBlocked) return 'danger'
  if (status === 'active') return 'success'
  if (status === 'pending_delete') return 'danger'
  return 'secondary'
}

export function peerLabel(status: string, isBlocked = false): string {
  if (isBlocked) return i18n.global.t('status.blocked')
  if (status === 'active') return i18n.global.t('status.active')
  if (status === 'pending') return i18n.global.t('status.pending')
  if (status === 'queued') return i18n.global.t('status.queued')
  if (status === 'pending_delete') return i18n.global.t('status.pendingDelete')
  if (status === 'deleted') return i18n.global.t('status.deleted')
  if (status === 'failed') return i18n.global.t('status.failed')
  if (status === 'error') return i18n.global.t('status.error')
  return status
}

export function operationSeverity(status: string): string {
  if (pendingOperationStatuses.has(status)) return 'warn'
  if (failedOperationStatuses.has(status)) return 'danger'
  if (status === 'succeeded') return 'success'
  return 'secondary'
}

export type NodeStage = 'ready' | 'offline' | 'applying_config' | 'syncing' | 'error'

export function getNodeStage(node: Node): NodeStage {
  if (failedOperationStatuses.has(node.provision_status) || node.last_error) {
    return 'error'
  }

  if (pendingOperationStatuses.has(node.provision_status) || node.provision_status !== 'succeeded') {
    return 'applying_config'
  }

  if (!node.reachable) return 'offline'

  if (failedOperationStatuses.has(node.sync_status) || node.sync_error) {
    return 'error'
  }

  if (pendingOperationStatuses.has(node.sync_status) || !node.last_synced_at) {
    return 'syncing'
  }

  return 'ready'
}

export function nodeStageSeverity(stage: NodeStage): string {
  if (stage === 'ready') return 'success'
  if (stage === 'error') return 'danger'
  if (stage === 'offline') return 'secondary'
  return 'warn'
}

export function nodeStageLabel(stage: NodeStage): string {
  return i18n.global.t(`nodeStage.${stage}`)
}

export function operationResolutionSeverity(state: string | null): string {
  if (state === 'recoverable') return 'warn'
  if (state === 'needs_manual_action') return 'danger'
  return 'secondary'
}

/**
 * Map a Remnawave user status to a PrimeVue Tag severity.
 *
 * @example remnawaveSeverity('ACTIVE') → 'success'
 */
export function remnawaveSeverity(status: string): string {
  if (status === 'ACTIVE') return 'success'
  if (status === 'DISABLED' || status === 'EXPIRED') return 'danger'
  return 'warn'
}

export function remnawaveBlockedReasonLabel(reason: string | null): string {
  if (reason === 'disabled') return i18n.global.t('status.disabled')
  if (reason === 'limited') return i18n.global.t('status.limited')
  if (reason === 'expired') return i18n.global.t('status.expired')
  if (reason === 'deleted') return i18n.global.t('status.deleted')
  return i18n.global.t('status.notBlocked')
}

export function remnawaveBlockedReasonSeverity(reason: string | null): string {
  if (reason === 'limited') return 'warn'
  if (reason) return 'danger'
  return 'success'
}

/**
 * Check whether a peer was online recently (within 3 minutes).
 */
export function isOnline(lastHandshake: string | null): boolean {
  if (!lastHandshake) return false
  return Date.now() - new Date(lastHandshake).getTime() < 180_000
}

/**
 * Build a tooltip string for a Remnawave user brief.
 */
export function remnawaveTooltip(rw: RemnawaveUserBrief): string {
  const parts: string[] = [`${i18n.global.t('remnawave.status')}: ${rw.status}`]
  if (rw.expire_at)
    parts.push(`${i18n.global.t('userDetail.labelExpires')}: ${fmtDate(rw.expire_at)}`)
  if (rw.traffic_limit_bytes > 0) {
    const used = fmtBytes(rw.combined_traffic_used_bytes)
    const limit = fmtBytes(rw.traffic_limit_bytes)
    parts.push(`${i18n.global.t('userDetail.labelTraffic')}: ${used} / ${limit}`)
  }
  return parts.join('\n')
}
