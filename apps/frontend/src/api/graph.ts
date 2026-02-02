
import api from './client'
import type { GraphSnapshot } from './types'

export async function getGraph(): Promise<GraphSnapshot>{
  const r = await api.get('/graph');
  return r.data
}
