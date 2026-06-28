import { req } from './client'
import type {
  TelegramProxyOperationResponse,
  TelegramProxySettings,
  TelegramProxySettingsUpdate,
  TelegramProxyStatus,
} from './types'

export const telegramProxyApi = {
  getTelegramProxySettings: () => req<TelegramProxySettings>('GET', '/telegram-proxy/settings'),
  getTelegramProxyStatus: () => req<TelegramProxyStatus>('GET', '/telegram-proxy/status'),
  updateTelegramProxySettings: (data: TelegramProxySettingsUpdate) =>
    req<TelegramProxySettings>('PUT', '/telegram-proxy/settings', data),
  applyTelegramProxy: () => req<TelegramProxyOperationResponse>('POST', '/telegram-proxy/apply'),
  disableTelegramProxy: () =>
    req<TelegramProxyOperationResponse>('POST', '/telegram-proxy/disable'),
  rotateTelegramProxySecret: () =>
    req<TelegramProxyOperationResponse>('POST', '/telegram-proxy/rotate-secret'),
}
