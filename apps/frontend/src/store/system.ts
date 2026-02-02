
import { create } from 'zustand'
import type { SystemState } from '../api/types'

type AuthState = { token?: string; setToken: (t?: string)=>void }

const initialToken = (typeof localStorage!=="undefined" && (localStorage.getItem("USER_API_KEY")||localStorage.getItem("USER_TOKEN"))) || "dev"

type K1Store = {
  auth: AuthState
  system: SystemState | null
  setSystem: (s: SystemState)=>void
}

export const useStore = create<K1Store>()((set)=>({
  auth: { token: initialToken, setToken: (t?: string)=> set((s)=> { try{ if(t){ localStorage.setItem('USER_TOKEN', t) } }catch(e){} return ({...s, auth: { ...s.auth, token: t }}) }) },
  system: null,
  setSystem: (s)=> set(()=>({system:s}))
}))

export const useAuth = { getState: ()=> useStore.getState().auth }
