import { create } from 'zustand'
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
  msgs: [{ role:'system', text:'Agent Zero HiL Wizard online. All comms are relayed through A0.', ts: new Date().toISOString()}],
  toggle: ()=> set(s=> ({...s, open: !s.open})),
  add: (m)=> set(s=> ({...s, msgs: [...s.msgs, m]})),
  ask: async (text: string)=>{
    const ts = new Date().toISOString()
    set(s=> ({...s, msgs: [...s.msgs, {role:'user', text, ts}], busy: true}))
    try{
      // Try backend proxy first
      const base = (localStorage.getItem('API_BASE') || 'http://localhost:8080')
      const r = await fetch(base + '/agent0/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ text }) })
      if(r.ok){
        const j = await r.json()
        set(s=> ({...s, msgs: [...s.msgs, {role:'assistant', text: (j.reply || 'Acknowledged.'), ts: new Date().toISOString()}]}))
      } else {
        // fallback
        set(s=> ({...s, msgs: [...s.msgs, {role:'assistant', text: 'Agent Zero relay offline. Using local hint: HiL gate enforces evidence and scope. Proceed to Operations.', ts: new Date().toISOString()}]}))
      }
    }catch(e){
      set(s=> ({...s, msgs: [...s.msgs, {role:'assistant', text: 'Agent Zero relay unreachable. Check backend /agent0/chat.', ts: new Date().toISOString()}]}))
    }finally{
      set({busy:false})
    }
  }
}))
