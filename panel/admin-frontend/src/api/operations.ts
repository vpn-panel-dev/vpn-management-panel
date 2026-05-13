import { req, reqBlob } from './client'
import type { TrafficPoint } from './types'

export const operationsApi = {
  sync: () => req<null>('POST', '/sync'),
  getUserTraffic: (uid: string, days = 30) =>
    req<TrafficPoint[]>('GET', `/users/${uid}/traffic?days=${days}`),
  fetchConfig: (uid: string, nid: string) => reqBlob(`/users/${uid}/configs/${nid}`),
  fetchConfigZip: (uid: string) => reqBlob(`/users/${uid}/configs/zip`),
  fetchQr: (uid: string, nid: string) => reqBlob(`/users/${uid}/qr/${nid}`),
  fetchQrAmnezia: (uid: string, nid: string) => reqBlob(`/users/${uid}/qr-amnezia/${nid}`),
}
