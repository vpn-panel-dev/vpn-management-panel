import type { RemnawaveUserBrief } from '../api/types'
import { fmtBytes, fmtDate } from './format'

/**
 * Map a peer status string to a PrimeVue Tag severity.
 *
 * @example peerSeverity('active') → 'success'
 */
export function peerSeverity(status: string): string {
  if (status === 'active') return 'success'
  if (status === 'pending_delete') return 'danger'
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
  if (reason === 'disabled') return 'Disabled'
  if (reason === 'limited') return 'Limited'
  if (reason === 'expired') return 'Expired'
  if (reason === 'deleted') return 'Deleted'
  return 'Not blocked'
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
  const parts: string[] = [`Статус: ${rw.status}`]
  if (rw.expire_at) parts.push(`Истекает: ${fmtDate(rw.expire_at)}`)
  if (rw.traffic_limit_bytes > 0) {
    const used = fmtBytes(rw.combined_traffic_used_bytes)
    const limit = fmtBytes(rw.traffic_limit_bytes)
    parts.push(`Combined traffic: ${used} / ${limit}`)
  }
  return parts.join('\n')
}
