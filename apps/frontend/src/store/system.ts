
import { create } from 'zustand'
import type { SystemState } from '../api/types'

type AuthState = { token?: string; setToken: (t?: string)=>void }

const initialToken =
  (typeof window !== "undefined" &&
    (sessionStorage.getItem("USER_TOKEN") || localStorage.getItem("USER_TOKEN"))) ||
  "dev"

type K1Store = {
  auth: AuthState
  system: SystemState | null
  setSystem: (s: SystemState)=>void
}

export const useStore = create<K1Store>()((set)=>({
  auth: { token: initialToken, setToken: (t?: string)=> set((s)=> { try{ if(t){ sessionStorage.setItem('USER_TOKEN', t) } else { sessionStorage.removeItem('USER_TOKEN') } }catch(e){} return ({...s, auth: { ...s.auth, token: t }}) }) },
  system: null,
  setSystem: (s)=> set(()=>({system:s}))
}))

export const useAuth = { getState: ()=> useStore.getState().auth }
