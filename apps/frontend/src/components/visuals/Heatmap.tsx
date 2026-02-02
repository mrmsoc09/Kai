import React from 'react'

type HeatmapProps = { rows?: number; cols?: number; data?: number[][] }
export default function Heatmap({rows=8, cols=16, data}: HeatmapProps){
  const vals = data || Array.from({length:rows}, ()=> Array.from({length:cols}, ()=> Math.random()))
  const cell = (v:number)=>{
    // gradient from cool (blue) to hot (purple/red)
    const hue = 200 - Math.round(160 * v) // 200→40
    const alpha = 0.15 + 0.65*v
    const bg = `hsla(${hue},70%,45%,${alpha})`
    const br = '1px solid var(--border)'
    return { background: bg, borderRight: br, borderBottom: br }
  }
  return <div style={{display:'grid', gridTemplateRows:`repeat(${rows}, 1fr)`, gap:2}}>
    {vals.map((r,i)=> <div key={i} style={{display:'grid', gridTemplateColumns:`repeat(${cols}, 1fr)`, gap:2}}>
      {r.map((v,j)=> <div key={j} style={{height:12, ...cell(v)}}/>) }
    </div>)}
  </div>
}
