
import api from './client'
import type { MCPServer } from './types'

export async function getServers(): Promise<MCPServer[]> {
  const r = await api.get('/mcp/servers')
  return r.data
}
