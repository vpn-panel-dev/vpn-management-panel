import { req } from './client'
import type {
  LocalAmneziawgTrafficSettings,
  LocalAmneziawgTrafficSettingsUpdate,
  RemnawaveSettings,
  RemnawaveSettingsUpdate,
  RemnawaveStatus,
  RemnawaveSyncResult,
  RemnawaveTestResult,
} from './types'

export const remnawaveApi = {
  getRemnawaveSettings: () => req<RemnawaveSettings>('GET', '/remnawave/settings'),
  getLocalTrafficSettings: () =>
    req<LocalAmneziawgTrafficSettings>('GET', '/remnawave/local-traffic/settings'),
  getRemnawaveStatus: () => req<RemnawaveStatus>('GET', '/remnawave/status'),
  updateRemnawaveSettings: (data: RemnawaveSettingsUpdate) =>
    req<RemnawaveSettings>('PUT', '/remnawave/settings', data),
  updateLocalTrafficSettings: (data: LocalAmneziawgTrafficSettingsUpdate) =>
    req<LocalAmneziawgTrafficSettings>('PUT', '/remnawave/local-traffic/settings', data),
  testRemnawaveConnection: () => req<RemnawaveTestResult>('POST', '/remnawave/test'),
  syncRemnawaveUsers: () => req<RemnawaveSyncResult>('POST', '/remnawave/sync'),
  syncRemnawaveUser: (userUuid: string) =>
    req<RemnawaveSyncResult>('POST', `/remnawave/users/${userUuid}/sync`),
}
