import { req } from './client'
import type { Node, NodeCreate, NodePeer, NodeUpdate } from './types'

export const nodesApi = {
  getNodes: () => req<Node[]>('GET', '/nodes'),
  addNode: (data: NodeCreate) => req<Node>('POST', '/nodes', data),
  updateNode: (id: string, data: NodeUpdate) => req<Node>('PATCH', `/nodes/${id}`, data),
  deleteNode: (id: string) => req<null>('DELETE', `/nodes/${id}`),
  provisionNode: (id: string) => req<null>('POST', `/nodes/${id}/provision`),
  getNodePeers: (nodeId: string) => req<NodePeer[]>('GET', `/nodes/${nodeId}/peers`),
}
