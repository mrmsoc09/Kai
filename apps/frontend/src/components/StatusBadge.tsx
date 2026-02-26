
import React from 'react'

export default function StatusBadge({ color, children }:{ color: 'green'|'orange'|'red'|'blue'|'gray', children: React.ReactNode }){
  return <span className={["badge", color].join(' ')}>{children}</span>
}
