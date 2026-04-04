import { create } from 'zustand'
import { api } from '../lib/api'
export type ChatMsg = { role: 'user'|'assistant'|'system'; text: string; ts: string }

type WizardState = {
  open: boolean
  busy: boolean
  msgs: ChatMsg[]
  toggle: ()=>void
  add: (m: ChatMsg)=>void
  ask: (text: string)=>Promise<void>
}

export const useWizard = create<WizardState>((set,get)=>({
  open: false,
  busy: false,
  msgs: [{ role:'system', text:'Kaison Composer HiL Wizard online. All comms are relayed through A0.', ts: new Date().toISOString()}],
  toggle: ()=> set(s=> ({...s, open: !s.open})),
  add: (m)=> set(s=> ({...s, msgs: [...s.msgs, m]})),
  ask: async (text: string)=>{
    const ts = new Date().toISOString()
    set(s=> ({...s, msgs: [...s.msgs, {role:'user', text, ts}], busy: true}))
    try{
      const r = await api.post('/agent0/chat', { text })
      const j = r.data || {}
      set(s=> ({...s, msgs: [...s.msgs, {role:'assistant', text: (j.reply || 'Acknowledged.'), ts: new Date().toISOString()}]}))
    }catch(e){
      set(s=> ({...s, msgs: [...s.msgs, {role:'assistant', text: 'Kaison Composer relay unreachable. Check backend /agent0/chat.', ts: new Date().toISOString()}]}))
    }finally{
      set({busy:false})
    }
  }
}))
