import { req } from './client'
import type { User } from './types'

export const usersApi = {
  getUsers: () => req<User[]>('GET', '/users'),
  addUser: (name: string) => req<User>('POST', '/users', { name }),
  blockUser: (id: string) => req<User>('PUT', `/users/${id}/block`),
  unblockUser: (id: string) => req<User>('PUT', `/users/${id}/unblock`),
  deleteUser: (id: string) => req<null>('DELETE', `/users/${id}`),
}
