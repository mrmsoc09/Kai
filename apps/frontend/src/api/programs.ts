import api from './client'

export type BBPProgram = {
  id: string
  name: string
  platform?: string
  program_url?: string
  scope_url?: string
  policy_url?: string
  payout_max_usd?: number|null
  exploitability_fit?: number
  priority_score?: number
}

export async function getTop50(): Promise<{ programs: BBPProgram[]; count: number; source?: string }>{
  const r = await api.get('/programs/bbp/top50')
  return r.data
}

export async function getTop10(): Promise<{ programs: BBPProgram[]; count: number; source?: string }>{
  const r = await api.get('/programs/bbp/top10')
  return r.data
}

export async function getValidation(): Promise<{ validation: any[]; available: boolean }>{
  const r = await api.get('/programs/bbp/top50/validation')
  return r.data
}

export async function queuePlan(target: string, chain?: string, auto: boolean = true){
  const r = await api.post('/programs/bbp/queue', { target, mode: 'plan', chain, auto })
  return r.data
}
