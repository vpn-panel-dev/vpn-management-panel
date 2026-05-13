import { req } from './client'
import type {
  RemnawaveSettings,
  RemnawaveSettingsUpdate,
  RemnawaveSyncResult,
  RemnawaveTestResult,
} from './types'

export const remnawaveApi = {
  getRemnawaveSettings: () => req<RemnawaveSettings>('GET', '/remnawave/settings'),
  updateRemnawaveSettings: (data: RemnawaveSettingsUpdate) =>
    req<RemnawaveSettings>('PUT', '/remnawave/settings', data),
  testRemnawaveConnection: () => req<RemnawaveTestResult>('POST', '/remnawave/test'),
  syncRemnawaveUsers: () => req<RemnawaveSyncResult>('POST', '/remnawave/sync'),
}
