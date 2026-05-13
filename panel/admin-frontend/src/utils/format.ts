/**
 * Format a byte count into a human-readable string.
 *
 * @example fmtBytes(1073741824) → "1.00 GB"
 */
export function fmtBytes(b: number): string {
  if (b >= 1073741824) return (b / 1073741824).toFixed(2) + ' GB'
  if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB'
  if (b >= 1024) return (b / 1024).toFixed(0) + ' KB'
  return b + ' B'
}

/**
 * Format an ISO date string into a localized date (ru-RU).
 *
 * @example fmtDate('2025-01-15T10:30:00Z') → "15.01.2025"
 */
export function fmtDate(iso: string | null): string {
  if (!iso) return '\u2014'
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  })
}

/**
 * Format an ISO date string into a localized date-time (ru-RU).
 *
 * @example formatDateTime('2025-01-15T10:30:00Z') → "15.01.2025, 10:30:00"
 */
export function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('ru-RU')
  } catch {
    return iso
  }
}

/**
 * Format a last-handshake timestamp as a relative time string (Russian).
 *
 * @example fmtHandshake('2025-01-15T10:30:00Z') → "5 мин. назад"
 */
export function fmtHandshake(lastHandshake: string | null): string {
  if (!lastHandshake) return '\u043D\u0438\u043A\u043E\u0433\u0434\u0430'
  const sec = Math.floor((Date.now() - new Date(lastHandshake).getTime()) / 1000)
  if (sec < 60) return `${sec} \u0441\u0435\u043A. \u043D\u0430\u0437\u0430\u0434`
  if (sec < 3600)
    return `${Math.floor(sec / 60)} \u043C\u0438\u043D. \u043D\u0430\u0437\u0430\u0434`
  if (sec < 86400) return `${Math.floor(sec / 3600)} \u0447. \u043D\u0430\u0437\u0430\u0434`
  return `${Math.floor(sec / 86400)} \u0434. \u043D\u0430\u0437\u0430\u0434`
}
