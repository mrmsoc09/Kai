import React, { useRef } from 'react'
import { useWizard } from '../../store/wizard'

export default function WizardPanel(){
  const { open, toggle, msgs, ask, busy } = useWizard()
  const inputRef = useRef<HTMLInputElement>(null)
  return <div className='wizard-wrap' data-open={open}>
    <div className='wizard-header'>
      <span>Kaison Composer — HiL Wizard</span>
      <button onClick={toggle}>Close</button>
    </div>
    <div className='wizard-body'>
      {msgs.map((m,i)=> <div key={i} className={'wline '+m.role}>
        <span className='ts'>{new Date(m.ts).toLocaleTimeString()}</span>
        <span className='role'>{m.role}</span>
        <span className='txt'>{m.text}</span>
      </div>)}
    </div>
    <div className='wizard-input'>
      <input ref={inputRef} placeholder='Ask Kaison Composer…' onKeyDown={e=>{ if(e.key==='Enter'){ const v=(e.target as HTMLInputElement).value; (e.target as HTMLInputElement).value=''; ask(v) }}} />
      <button disabled={busy} onClick={()=>{ const v=inputRef.current?.value||''; if(!v) return; inputRef.current!.value=''; ask(v) }}>{busy? '…':'Send'}</button>
    </div>
  </div>
}
