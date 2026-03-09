import React from 'react'
export default function NeonChip({color='purple', children}:{color?:'purple'|'orange'|'green'|string, children: React.ReactNode}){
  return <span className={`neon-chip ${color}`}>{children}</span>
}
