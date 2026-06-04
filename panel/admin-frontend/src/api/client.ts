import { i18n } from '../i18n'
import type { LoginResponse } from './types'

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}`, ...extra } : { ...extra }
}

function handleUnauthorized(): void {
  localStorage.removeItem('token')
  window.location.href = '/login'
}

export async function req<T>(method: string, path: string, body?: unknown): Promise<T | null> {
  const headers = authHeaders(body ? { 'Content-Type': 'application/json' } : {})

  const res = await fetch(`/api${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    handleUnauthorized()
    return null
  }

  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`)
    throw new Error(text)
  }
  if (res.status === 204) return null
  return res.json() as Promise<T>
}

export async function reqBlob(path: string): Promise<Blob | null> {
  const res = await fetch(`/api${path}`, { headers: authHeaders() })
  if (res.status === 401) {
    handleUnauthorized()
    return null
  }
  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`)
    throw new Error(text)
  }
  return res.blob()
}

export async function login(password: string): Promise<LoginResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
  const data = (await res.json()) as LoginResponse & { detail?: string }
  if (!res.ok) throw new Error(data.detail || i18n.global.t('login.error'))
  return data
}
