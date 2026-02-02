
import React, { useEffect, useState } from "react";

type Note = { id: string; title?: string; path?: string; classification?: string; type?: string };

export default function Knowledge(){
  const [status, setStatus] = useState<any>({});
  const [notes, setNotes] = useState<Note[]>([]);
  const [count, setCount] = useState<number>(0);

  const load = ()=>{
    fetch("/knowledge/status").then(r=>r.json()).then(setStatus).catch(()=>setStatus({}));
    fetch("/knowledge/notes").then(r=>r.json()).then((d)=>{ setNotes(d.notes||[]); setCount(d.count||0); }).catch(()=>{ setNotes([]); setCount(0); });
  };

  useEffect(()=>{ load(); },[]);

  const refresh = ()=>{
    fetch("/knowledge/refresh",{method:"POST"}).then(()=>load());
  };

  return (
    <div style={{padding:16}}>
      <h2>Knowledge</h2>
      <div style={{marginBottom:12}}>
        <div>Enabled: <strong>{String(status.enabled)}</strong></div>
        <div>Vault: <code>{status.vault_path||"-"}</code></div>
        <button onClick={refresh} style={{marginTop:8}}>Refresh Vault Index</button>
      </div>
      <div>
        <h3>Notes ({count})</h3>
        {(notes||[]).map(n=> (
          <div key={n.id} style={{border:"1px solid #eee", borderRadius:8, padding:8, marginBottom:8}}>
            <div><strong>{n.title||n.id}</strong> <span style={{fontSize:12, color:"#666"}}>({n.type})</span></div>
            <div style={{fontSize:12}}>{n.classification} • <code>{n.path}</code></div>
          </div>
        ))}
      </div>
    </div>
  );
}
