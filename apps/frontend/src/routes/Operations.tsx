import React, { useState } from 'react'
import { createFinding, addEvidence, requestHIL, approveHIL, submitFinding } from '../lib/api'

export default function Operations(){
  const [fid, setFid] = useState('')
  const [log, setLog] = useState<string[]>([])
  const [program, setProgram] = useState('google_vrp')
  const [asset, setAsset] = useState('scope')
  const [title, setTitle] = useState('smoke finding')
  const [desc, setDesc] = useState('infra smoke')
  const [severity, setSeverity] = useState('LOW')

  const append = (m:string)=> setLog(x=>[...x, m])

  async function doCreate(){
    try{
      const r = await createFinding({program, asset, title, description:desc, severity})
      const id = r.data.id
      setFid(id)
      append(`Created finding: ${id}`)
    }catch(e:any){ append('Create error: '+(e?.message||'err')) }
  }
  async function doEvidence(){
    if(!fid) return append('No finding id')
    try{
      await addEvidence(fid,{kind:'http_trace', uri:'file:///artifacts/trace1.json', sha256_hex:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'})
      append('Added evidence')
    }catch(e:any){ append('Evidence error: '+(e?.message||'err')) }
  }
  async function doRequest(){
    if(!fid) return append('No finding id')
    try{ await requestHIL(fid, 'ready'); append('Requested HiL') }catch(e:any){ append('Request error: '+(e?.message||'err')) }
  }
  async function doApprove(){
    if(!fid) return append('No finding id')
    try{ await approveHIL(fid); append('Approved HiL') }catch(e:any){ append('Approve error: '+(e?.message||'err')) }
  }
  async function doSubmit(){
    if(!fid) return append('No finding id')
    try{ await submitFinding(fid,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'); append('Submitted (TheHive)') }catch(e:any){ append('Submit error (expected if TheHive key missing): '+(e?.message||'err')) }
  }

  return <div style={{padding:16}}>
    <h2>Operations — HiL flow</h2>
    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
      <div>
        <div><label>Program <input value={program} onChange={e=>setProgram(e.target.value)}/></label></div>
        <div><label>Asset <input value={asset} onChange={e=>setAsset(e.target.value)}/></label></div>
        <div><label>Title <input value={title} onChange={e=>setTitle(e.target.value)} style={{width:'100%'}}/></label></div>
        <div><label>Description <input value={desc} onChange={e=>setDesc(e.target.value)} style={{width:'100%'}}/></label></div>
        <div><label>Severity <input value={severity} onChange={e=>setSeverity(e.target.value)}/></label></div>
        <div style={{marginTop:10}}>
          <button onClick={doCreate}>Create Finding</button>
          <button onClick={doEvidence} style={{marginLeft:8}}>Add Evidence</button>
          <button onClick={doRequest} style={{marginLeft:8}}>Request HiL</button>
          <button onClick={doApprove} style={{marginLeft:8}}>Approve (admin)</button>
          <button onClick={doSubmit} style={{marginLeft:8}}>Submit</button>
        </div>
      </div>
      <div>
        <h4>Log</h4>
        <pre style={{background:'#111',color:'#0f0',padding:8,minHeight:240}}>{log.join('\n')}</pre>
      </div>
    </div>
  </div>
}
