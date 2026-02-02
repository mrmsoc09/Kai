
import React, { useEffect, useState } from 'react'
import { getPersonas } from '../../api/personas'
import type { Persona } from '../../api/types'
import PersonaCard from './PersonaCard'

export default function PersonaGrid(){
  const [rows, setRows] = useState<Persona[]>([])
  useEffect(()=>{ getPersonas().then(setRows).catch(()=> setRows([])) },[])
  return <div className='persona-grid'>
    {rows.map(p=> <PersonaCard key={p.id} p={p} />)}
  </div>
}
