
import React from 'react'
export default function AgentIcon({className}:{className?:string}){
  return <svg className={className||'icon'} viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='1.5'>
    <circle cx='12' cy='8' r='4'/>
    <path d='M4 20c0-4 4-6 8-6s8 2 8 6'/>
  </svg>
}
