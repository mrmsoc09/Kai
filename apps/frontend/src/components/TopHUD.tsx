import React, { useEffect, useState } from 'react'
import GradientLogo from './common/GradientLogo'
import NeonChip from './common/NeonChip'
import axios from 'axios'
import { getApiKeyStatus } from '../lib/api'

export default function TopHUD(){
  const [health, setHealth] = useState<'OK'|'DOWN'|'...'>('...')
  const [ws, setWs] = useState<'ON'|'OFF'>('OFF')
  const API = (import.meta.env.VITE_API_BASE || (localStorage.getItem('API_BASE')||'http://localhost:8080'))

  useEffect(()=>{
    let t: any
    const check = async()=>{
      try{ await axios.get(API + '/healthz', { timeout: 2000 }); setHealth('OK') }
      catch{ setHealth('DOWN') }
      t = setTimeout(check, 4000)
    }
    check()
    return ()=> { if(t) clearTimeout(t) }
  },[])

  useEffect(()=>{
    // Lightweight WS probe if backend exposes /ws (will noop otherwise)
    try{
      const wsurl = API.replace('http','ws') + '/ws?token=dev'
      const w = new WebSocket(wsurl)
      w.onopen = ()=> setWs('ON')
      w.onclose = ()=> setWs('OFF')
      return ()=> { try{ w.close() }catch(e){} }
    }catch(e){ setWs('OFF') }
  },[])

  const { userKeySet, adminKeySet } = getApiKeyStatus()

  return <div className='topbar'>
    <div className='left'>
      <GradientLogo/>
      <NeonChip color='purple'>Hacker Persona</NeonChip>
      <NeonChip color={health==='OK'? 'teal':'cyan'}>API {health}</NeonChip>
      <NeonChip color={ws==='ON'? 'teal':'cyan'}>WS {ws}</NeonChip>
    </div>
    <div className='right'>
      <NeonChip color={userKeySet? 'teal':'cyan'}>UserKey {userKeySet? 'SET':'MISSING'}</NeonChip>
      <NeonChip color={adminKeySet? 'teal':'cyan'}>AdminKey {adminKeySet? 'SET':'MISSING'}</NeonChip>
    </div>
  </div>
}
