
import React, { useEffect, useState } from 'react'
import { getServers } from '../../api/mcp'
import type { MCPServer } from '../../api/types'

function fmtUptime(s:number){
  const d = Math.floor(s/86400); s%=86400; const h=Math.floor(s/3600); s%=3600; const m=Math.floor(s/60)
  const parts=[] as string[]; if(d) parts.push(d+'d'); if(h) parts.push(h+'h'); if(m) parts.push(m+'m'); return parts.join(' ')||'0m'
}

export default function Rack(){
  const [list, setList] = useState<MCPServer[]>([])
  useEffect(()=>{ getServers().then(setList).catch(()=> setList([])) },[])
  return <div className='rack'>
    {list.map(s=> <div key={s.id} className='rack-unit'>
      <div className='ru-left'>
        <span className={'light '+s.status}></span>
        <div>
          <div style={{fontSize:13}}>{s.name}</div>
          <div className='purpose'>{s.purpose}</div>
        </div>
      </div>
      <div className='uptime'>{fmtUptime(s.uptime_seconds)}</div>
    </div>)}
  </div>
}
