
import React, { useEffect, useRef } from 'react'

export default function Sparkline({values}:{values:number[]}){
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(()=>{
    const cvs = ref.current; if(!cvs) return
    const dpr = window.devicePixelRatio||1
    const w = cvs.clientWidth||120, h = cvs.clientHeight||36
    cvs.width = Math.round(w*dpr); cvs.height = Math.round(h*dpr)
    const ctx = cvs.getContext('2d')!
    ctx.setTransform(dpr,0,0,dpr,0,0)
    ctx.clearRect(0,0,w,h)
    if(!values?.length) return
    const min = Math.min(...values), max = Math.max(...values)
    const pad = 6
    const sx = (i:number)=> pad + (w-2*pad)*(i/(values.length-1||1))
    const sy = (v:number)=> h - pad - ((h-2*pad) * (max===min? 0.5 : (v-min)/(max-min)))
    ctx.strokeStyle = '#a9c4e0'; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(sx(0), sy(values[0]))
    for(let i=1;i<values.length;i++){ ctx.lineTo(sx(i), sy(values[i])) }
    ctx.stroke()
  }, [values])
  return <canvas className='spark' ref={ref} aria-label='Confidence trend sparkline' />
}
