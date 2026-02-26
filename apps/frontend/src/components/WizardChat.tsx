import React, { useState } from 'react';
const apiBase = import.meta.env.VITE_API_BASE || '';

type Msg = { role: 'user'|'assistant', text: string };

export default function WizardChat(){
  const [msgs, setMsgs] = useState<Msg[]>([{role:'assistant', text:'I am Agent Zero – your HiL wizard. How can I assist?' }]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async ()=>{
    const t = input.trim(); if(!t||busy) return; setInput(''); setMsgs(m=>[...m,{role:'user', text:t}]); setBusy(true);
    try{
      const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN');
      const r = await fetch(apiBase + '/agent0/chat', { method:'POST', headers:{'Content-Type':'application/json', ...(tok? { Authorization: 'Bearer ' + tok } : {})}, body: JSON.stringify({text: t})});
      const j = await r.json();
      const reply = j.reply || '...';
      setMsgs(m=>[...m,{role:'assistant', text: reply}]);
    }catch(err){
      setMsgs(m=>[...m,{role:'assistant', text: 'Agent Zero relay offline. Try again later.'}]);
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
