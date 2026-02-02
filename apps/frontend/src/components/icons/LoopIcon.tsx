
import React from 'react'
export default function LoopIcon({className}:{className?:string}){
  return <svg className={className||'icon'} viewBox='0 0 24 24' fill='none' stroke='currentColor' strokeWidth='1.5'>
    <path d='M3 8a9 9 0 0 1 15-3' />
    <polyline points='18 5 18 12 11 12' />
    <path d='M21 16a9 9 0 0 1-15 3' />
    <polyline points='6 19 6 12 13 12' />
  </svg>
}
