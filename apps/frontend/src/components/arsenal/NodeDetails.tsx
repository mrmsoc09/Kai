
import React from 'react'
import type { GraphNode } from '../../api/types'

export default function NodeDetails({node, onClose}:{node?: GraphNode|null, onClose: ()=>void}){
  if(!node) return null
  return <div className='details-panel'>
    <div className='details-title'>{node.label || node.id}</div>
    <div className='details-sub'>Risk: {node.risk.toUpperCase()} • Importance: {node.importance}</div>
    {node.role && <div className='details-sub'>Role: {node.role}</div>}
    <div style={{display:'flex', gap:8, marginTop:8}}>
      <button className='k1-btn' onClick={onClose}>Close</button>
    </div>
  </div>
}
