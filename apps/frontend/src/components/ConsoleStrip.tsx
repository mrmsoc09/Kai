
import React, { useEffect, useRef, useState } from 'react'
import { useStore } from '../store/system'
import { connectWS } from '../api/ws'

export default function ConsoleStrip(){
  const token = useStore(s=> s.auth.token)
  const [lines, setLines] = useState<{ts:string,msg:string}[]>([])
  const ref = useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if(!token) { setLines([]); return }
    const ws = connectWS(token)
    ws.onmessage = (ev)=>{
      const ts = new Date().toISOString()
      setLines(prev=> [...prev.slice(-49), {ts, msg: typeof ev.data==='string'? ev.data : '[event]'}])
    }
    return ()=> { try{ws.close()}catch(e){} }
  }, [token])
  useEffect(()=>{
    if(ref.current){ ref.current.scrollTop = ref.current.scrollHeight }
  }, [lines])
  return <div className='console'>
    <div className='console-inner' ref={ref}>
      {lines.map((l,i)=> <div key={i} className='console-line'>
        <span className='ts'>{l.ts}</span>
        <span className='msg'>{l.msg}</span>
      </div>)}
    </div>
  </div>
}
