
import React, { useEffect, useState } from 'react'
import GraphCanvas from './GraphCanvas'
import NodeDetails from './NodeDetails'
import { getGraph } from '../../api/graph'
import type { GraphSnapshot, GraphNode } from '../../api/types'

const FALLBACK: GraphSnapshot = {
  center_id: 'TARGET',
  nodes: [
    {id:'TARGET', label:'TARGET', risk:'blue', importance:5, role:'target'},
    {id:'svc1', label:'API Gateway', risk:'amber', importance:4, role:'service'},
    {id:'asset1', label:'S3 Bucket', risk:'red', importance:4, role:'asset'},
    {id:'idp1', label:'IDP', risk:'blue', importance:3, role:'identity'},
    {id:'host1', label:'Edge Host', risk:'amber', importance:3, role:'asset'},
    {id:'sub1', label:'Subdomain A', risk:'gray', importance:2, role:'asset'},
  ],
  edges: [
    {id:'e1', source:'TARGET', target:'svc1', kind:'proven'},
    {id:'e2', source:'svc1', target:'asset1', kind:'hypothesis'},
    {id:'e3', source:'TARGET', target:'idp1', kind:'proven'},
    {id:'e4', source:'host1', target:'svc1', kind:'active'},
    {id:'e5', source:'sub1', target:'host1', kind:'hypothesis'},
  ]
}

export default function ArsenalView(){
  const [data, setData] = useState<GraphSnapshot|null>(null)
  const [selected, setSelected] = useState<GraphNode|null>(null)

  useEffect(()=>{
    getGraph().then(setData).catch(()=> setData(FALLBACK))
  },[])

  return <div className='arsenal-wrap widget' aria-label='Arsenal attack graph'>
    <GraphCanvas data={data||FALLBACK} onSelect={setSelected} />
    <div className='legend'>
      <span className='chip'>— proven</span>
      <span className='chip' style={{borderStyle:'dashed'}}>— hypothesized</span>
      <span className='chip'>⟲ active</span>
    </div>
    <NodeDetails node={selected} onClose={()=> setSelected(null)} />
  </div>
}
