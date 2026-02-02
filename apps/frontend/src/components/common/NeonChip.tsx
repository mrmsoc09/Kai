import React from 'react'
export default function NeonChip({color='purple', children}:{color?:'purple'|'cyan'|'teal'|string, children: React.ReactNode}){
  return <span className={`neon-chip ${color}`}>{children}</span>
}
