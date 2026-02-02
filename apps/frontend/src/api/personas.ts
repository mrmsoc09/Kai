
import api from './client'
import type { Persona } from './types'

export async function getPersonas(): Promise<Persona[]> {
  const r = await api.get('/personas/')
  return r.data
}
