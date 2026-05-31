import { req, reqBlob } from './client'
import type {
  LocalAmneziawgNodeUsageTotals,
  LocalAmneziawgUsageDailyTotals,
  LocalAmneziawgUsageNodeDailyTotals,
  LocalAmneziawgUsageNodeTotals,
  LocalAmneziawgUsageTotals,
  TrafficPoint,
} from './types'

export const operationsApi = {
  sync: () => req<null>('POST', '/sync'),
  getUserTraffic: (uid: string, days = 30) =>
    req<TrafficPoint[]>('GET', `/users/${uid}/traffic?days=${days}`),
  getUserLocalTraffic: (uid: string) =>
    req<LocalAmneziawgUsageTotals>('GET', `/users/${uid}/local-traffic`),
  getUserLocalTrafficDaily: (uid: string, days = 30) =>
    req<LocalAmneziawgUsageDailyTotals[]>('GET', `/users/${uid}/local-traffic/daily?days=${days}`),
  getUserLocalTrafficNodes: (uid: string) =>
    req<LocalAmneziawgUsageNodeTotals[]>('GET', `/users/${uid}/local-traffic/nodes`),
  getUserLocalTrafficNodesDaily: (uid: string, days = 30) =>
    req<LocalAmneziawgUsageNodeDailyTotals[]>(
      'GET',
      `/users/${uid}/local-traffic/nodes/daily?days=${days}`,
    ),
  getNodeLocalTraffic: (nodeId: string) =>
    req<LocalAmneziawgNodeUsageTotals>('GET', `/nodes/${nodeId}/local-traffic`),
  fetchConfig: (uid: string, nid: string) => reqBlob(`/users/${uid}/configs/${nid}`),
  fetchConfigZip: (uid: string) => reqBlob(`/users/${uid}/configs/zip`),
  fetchQr: (uid: string, nid: string) => reqBlob(`/users/${uid}/qr/${nid}`),
  fetchQrAmnezia: (uid: string, nid: string) => reqBlob(`/users/${uid}/qr-amnezia/${nid}`),
}
