import { req } from './client'
import type {
  LocalUserLifecycleUpdate,
  RegeneratedPublicLink,
  User,
  UserListFacets,
  UserListQuery,
  UserListResponse,
} from './types'

const DAY_MS = 24 * 60 * 60 * 1000

function isExpiring(user: User): boolean {
  const expireAt = user.remnawave?.expire_at ?? user.lifecycle?.expire_at ?? user.expire_at
  if (!expireAt) return false
  const expiresAt = new Date(expireAt).getTime()
  return (
    Number.isFinite(expiresAt) && expiresAt > Date.now() && expiresAt - Date.now() <= 14 * DAY_MS
  )
}

function isExpired(user: User): boolean {
  if (
    user.is_blocked &&
    (user.remnawave?.blocked_reason === 'expired' || user.lifecycle?.blocked_reason === 'expired')
  ) {
    return true
  }
  const expireAt = user.remnawave?.expire_at ?? user.lifecycle?.expire_at ?? user.expire_at
  if (!expireAt) return false
  const expiresAt = new Date(expireAt).getTime()
  return Number.isFinite(expiresAt) && expiresAt <= Date.now()
}

function hasSyncIssue(user: User): boolean {
  return (
    !!user.remnawave && (user.remnawave.sync_status !== 'synced' || !!user.remnawave.sync_error)
  )
}

function trafficValue(user: User): number {
  if (user.remnawave) return user.remnawave.combined_traffic_used_bytes
  return user.local_traffic?.total_bytes ?? 0
}

function userDisplayName(user: User): string {
  return user.remnawave?.display_name ?? user.name
}

function userSearchText(user: User): string {
  return [
    userDisplayName(user),
    user.name,
    user.vpn_ip,
    user.id,
    user.remnawave?.uuid,
    user.remnawave?.username,
    user.remnawave?.email,
    user.remnawave?.tag,
    user.remnawave?.sync_reason,
    user.remnawave?.sync_error,
    ...user.peers.map((peer) => `${peer.node_name} ${peer.endpoint ?? ''} ${peer.status}`),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

function buildFacets(users: User[]): UserListFacets {
  return {
    total: users.length,
    online: users.filter((user) => user.online).length,
    blocked: users.filter((user) => user.is_blocked).length,
    local: users.filter((user) => !user.remnawave).length,
    remnawave: users.filter((user) => user.remnawave).length,
    syncIssues: users.filter(hasSyncIssue).length,
    expiring: users.filter(isExpiring).length,
  }
}

function applyUserQuery(users: User[], query: UserListQuery): UserListResponse {
  const search = query.search.trim().toLowerCase()
  let filtered = users.filter((user) => {
    if (query.source === 'local' && user.remnawave) return false
    if (query.source === 'remnawave' && !user.remnawave) return false
    if (query.status === 'active' && user.is_blocked) return false
    if (query.status === 'blocked' && !user.is_blocked) return false
    if (query.status === 'expired' && !isExpired(user)) return false
    if (query.status === 'expiring' && !isExpiring(user)) return false
    if (query.status === 'sync_issues' && !hasSyncIssue(user)) return false
    return !search || userSearchText(user).includes(search)
  })

  filtered = [...filtered].sort((a, b) => {
    if (query.sort === 'source') return Number(!!b.remnawave) - Number(!!a.remnawave)
    if (query.sort === 'status') return Number(b.is_blocked) - Number(a.is_blocked)
    if (query.sort === 'traffic') return trafficValue(b) - trafficValue(a)
    if (query.sort === 'expiration') {
      return (
        (Date.parse(a.remnawave?.expire_at ?? a.lifecycle?.expire_at ?? a.expire_at ?? '') ||
          Infinity) -
        (Date.parse(b.remnawave?.expire_at ?? b.lifecycle?.expire_at ?? b.expire_at ?? '') ||
          Infinity)
      )
    }
    if (query.sort === 'sync') return Number(hasSyncIssue(b)) - Number(hasSyncIssue(a))
    return userDisplayName(a).localeCompare(userDisplayName(b), 'ru')
  })

  const safePageSize = Math.max(10, query.pageSize)
  const safePage = Math.max(1, query.page)
  const start = (safePage - 1) * safePageSize

  return {
    items: filtered.slice(start, start + safePageSize),
    total: filtered.length,
    page: safePage,
    pageSize: safePageSize,
    facets: buildFacets(users),
  }
}

export const usersApi = {
  getUsers: () => req<User[]>('GET', '/users'),
  getUserList: async (query: UserListQuery) => {
    const users = (await req<User[]>('GET', '/users')) ?? []
    return applyUserQuery(users, query)
  },
  queryLocalUsers: applyUserQuery,
  addUser: (name: string) => req<User>('POST', '/users', { name }),
  blockUser: (id: string) => req<User>('PUT', `/users/${id}/block`),
  unblockUser: (id: string) => req<User>('PUT', `/users/${id}/unblock`),
  updateLifecycle: (id: string, data: LocalUserLifecycleUpdate) =>
    req<User>('PUT', `/users/${id}/lifecycle`, data),
  resetTraffic: (id: string) => req<User>('POST', `/users/${id}/lifecycle/reset-traffic`),
  regeneratePublicLink: (id: string) =>
    req<RegeneratedPublicLink>('POST', `/users/${id}/public-link/regenerate`),
  deleteUser: (id: string) => req<null>('DELETE', `/users/${id}`),
}
