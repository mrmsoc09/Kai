
import api from './client'
import type { Finding, ChainPotential, Stage } from './types'

export async function getFindings(filters?: {chain_potential?: ChainPotential, stage?: Stage}): Promise<Finding[]> {
  const r = await api.get('/intel/findings', { params: filters||{} })
  return r.data
}
