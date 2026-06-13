import { i18n } from '../i18n'

/**
 * Format a byte count into a human-readable string.
 *
 * @example fmtBytes(1073741824) → "1.00 GB"
 */
export function fmtBytes(b: number): string {
  if (b >= 1073741824) return `${(b / 1073741824).toFixed(2)} GB`
  if (b >= 1048576) return `${(b / 1048576).toFixed(1)} MB`
  if (b >= 1024) return `${(b / 1024).toFixed(0)} KB`
  return `${b} B`
}

function resolveBrowserLocale(locale: string): string {
  if (locale === 'zh') return 'zh-CN'
  return locale
}

/**
 * Format an ISO date string into a localized date.
 *
 * @example fmtDate('2025-01-15T10:30:00Z') → "15.01.2025"
 */
export function fmtDate(iso: string | null): string {
  if (!iso) return '\u2014'
  const locale = resolveBrowserLocale(i18n.global.locale.value)
  return new Date(iso).toLocaleDateString(locale, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

/**
 * Format an ISO date string into a localized date-time.
 *
 * @example formatDateTime('2025-01-15T10:30:00Z') → "15.01.2025, 10:30:00"
 */
export function formatDateTime(iso: string): string {
  try {
    const locale = resolveBrowserLocale(i18n.global.locale.value)
    return new Date(iso).toLocaleString(locale)
  } catch {
    return iso
  }
}

/**
 * Format a last-handshake timestamp as a relative time string.
 *
 * @example fmtHandshake('2025-01-15T10:30:00Z') → "5 мин. назад"
 */
export function fmtHandshake(lastHandshake: string | null): string {
  if (!lastHandshake) return i18n.global.t('time.never')
  const timestamp = new Date(lastHandshake).getTime()
  if (!Number.isFinite(timestamp) || timestamp <= 0) return i18n.global.t('time.never')
  const sec = Math.floor((Date.now() - timestamp) / 1000)
  if (sec < 0) return i18n.global.t('time.never')
  if (sec < 60) return i18n.global.t('time.secondsAgo', { n: sec })
  if (sec < 3600) return i18n.global.t('time.minutesAgo', { n: Math.floor(sec / 60) })
  if (sec < 86400) return i18n.global.t('time.hoursAgo', { n: Math.floor(sec / 3600) })
  return i18n.global.t('time.daysAgo', { n: Math.floor(sec / 86400) })
}
