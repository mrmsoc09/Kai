
import { create } from 'zustand'
import type { SystemState } from '../api/types'

export type UserProfile = {
  id: string
  roles: string[]
  tenant_id?: string
}

type AuthState = {
  token: string | null
  user: UserProfile | null
}

type K1Store = {
  auth: AuthState
  system: SystemState | null
  llmConfig: any | null
  login: (token: string, user: UserProfile) => void
  logout: () => void
  setSystem: (s: SystemState) => void
  setLLMConfig: (config: any) => void
}

export const useStore = create<K1Store>()((set) => ({
  auth: { token: null, user: null },
  system: null,
  llmConfig: null,
  login: (token, user) => set((s) => ({ ...s, auth: { token, user } })),
  logout: () => set((s) => ({ ...s, auth: { token: null, user: null }, llmConfig: null })),
  setSystem: (s) => set(() => ({ system: s })),
  setLLMConfig: (config) => set(() => ({ llmConfig: config })),
}))

// Backward-compat shim.
// api/client.ts:  useAuth.getState().token            (object access)
// UnifiedOrchestrationDashboard: useAuth().getState().token  (function call)
// This shim satisfies both patterns.
const _authShim = {
  getState: () => ({
    token: useStore.getState().auth.token ?? undefined,
  }),
}
export const useAuth: typeof _authShim & (() => typeof _authShim) =
  Object.assign(() => _authShim, _authShim)
