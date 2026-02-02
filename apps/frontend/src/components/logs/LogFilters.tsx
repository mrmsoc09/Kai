
import React from 'react'
import type { LogCategory, LogType } from '../../api/types'

type Props = { q: string, onQ: (s:string)=>void, category: LogCategory|'' , onCategory: (c:LogCategory|'')=>void }

const cats: (LogCategory|'')[] = ['', 'plan','execution','evidence','governance','audit','metrics','learning']

export default function LogFilters({q,onQ,category,onCategory}: Props){
  return <div className='log-controls'>
    <input placeholder='Search logs' value={q} onChange={e=> onQ(e.target.value)} />
    <select value={category} onChange={e=> onCategory((e.target.value||'') as any)}>
      {cats.map(c=> <option key={String(c)} value={c||''}>{c? c: 'all categories'}</option>)}
    </select>
  </div>
}
