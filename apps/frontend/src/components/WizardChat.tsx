import React, { useState } from 'react';
import { api } from '../lib/api';

type Msg = { role: 'user'|'assistant', text: string };

export default function WizardChat(){
  const [msgs, setMsgs] = useState<Msg[]>([{role:'assistant', text:'I am Kaison Composer – your HiL wizard. How can I assist?' }]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async ()=>{
    const t = input.trim(); if(!t||busy) return; setInput(''); setMsgs(m=>[...m,{role:'user', text:t}]); setBusy(true);
    try{
      const r = await api.post('/agent0/chat', { text: t });
      const j = r.data || {};
      const reply = j.reply || '...';
      setMsgs(m=>[...m,{role:'assistant', text: reply}]);
    }catch(err){
      setMsgs(m=>[...m,{role:'assistant', text: 'Kaison Composer relay offline. Try again later.'}]);
    }finally{ setBusy(false); }
  };
  return (
    <div className='flex flex-col h-full'>
      <div className='flex-1 overflow-auto space-y-2 p-3 bg-black/40 rounded border border-slate-800'>
        {msgs.map((m,i)=> (
          <div key={i} className={'max-w-[80%] px-3 py-2 rounded ' + (m.role==='user' ? 'ml-auto bg-cyan-900/40 text-cyan-200' : 'mr-auto bg-purple-900/30 text-purple-200') }>
            {m.text}
          </div>
        ))}
      </div>
      <div className='mt-2 flex gap-2'>
        <input className='flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 outline-none focus:border-cyan-500' placeholder='Type a message...' value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=> e.key==='Enter' && send()} />
        <button onClick={send} disabled={busy} className='px-4 py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50'>Send</button>
      </div>
    </div>
  );
}
