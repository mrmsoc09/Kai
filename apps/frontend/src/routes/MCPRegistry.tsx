import React, { useEffect, useState } from 'react'
import { getProviderCatalog, getProviderSelection, setProviderSelection } from '../lib/api'

export default function MCPRegistry(){
  const [market, setMarket] = useState('healthcare')
  const [providers, setProviders] = useState<any[]>([])
  const [selected, setSelected] = useState<string[]>([])

  async function load(){
    const cat = await getProviderCatalog(market)
    setProviders(cat.data.providers || [])
    const sel = await getProviderSelection(market)
    setSelected(sel.data.selected_ids || [])
  }
  useEffect(()=>{ load().catch(()=>{}) },[market])

  function toggle(id:string){ setSelected(x=> x.includes(id)? x.filter(i=>i!==id): [...x,id]) }
  async function save(){ await setProviderSelection(market, selected) }

  return <div style={{padding:16}}>
    <h2>Provider Registry</h2>
    <div>Market: <select value={market} onChange={e=>setMarket(e.target.value)}>
      <option value='healthcare'>healthcare</option>
      <option value='finance'>finance</option>
      <option value='ecommerce'>ecommerce</option>
      <option value='government_contracts_grants'>government_contracts_grants</option>
      <option value='supply_chain'>supply_chain</option>
      <option value='cross'>cross</option>
    </select> <button onClick={save}>Save Selection</button></div>
    <ul>
      {providers.map(p=> <li key={p.id}>
        <label><input type='checkbox' checked={selected.includes(p.id)} onChange={()=>toggle(p.id)} /> {p.name} — <code>{p.id}</code> ({p.market})</label>
      </li>)}
    </ul>
  </div>
}
