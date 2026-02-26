
import React, { useEffect, useRef, useState } from 'react'
import type { GraphSnapshot, GraphNode, GraphEdge, RiskColor, EdgeKind } from '../../api/types'
import { applyTransform, screenToWorld, Viewport } from './panzoom'

const COLORS: Record<RiskColor,string> = {
  green: '#9ad1b1', amber: '#e0c084', red: '#e0a9a9', blue: '#a9c4e0', gray: '#b0b6bc'
}

function nodeRadius(n: GraphNode){
  const base = 10; const scale = 3; const imp = Math.max(1, Math.min(5, n.importance||2))
  return base + scale * imp
}

function computeLayout(g: GraphSnapshot, w:number, h:number){
  // Spider web radial layout
  const centerId = g.center_id || g.nodes[0]?.id
  const center = g.nodes.find(n=> n.id===centerId)
  const centerPos: Record<string,{x:number,y:number}> = {}
  const cx = w/2, cy = h/2
  centerPos[centerId||'center'] = {x: cx, y: cy}
  // BFS rings
  const adj: Record<string, string[]> = {}
  g.edges.forEach(e=>{ (adj[e.source] ||= []).push(e.target); (adj[e.target] ||= []).push(e.source) })
  const dist: Record<string, number> = {}
  const q: string[] = []
  if(centerId){ dist[centerId]=0; q.push(centerId) }
  while(q.length){
    const cur = q.shift()!; const d = dist[cur]
    for(const nb of (adj[cur]||[])) if(dist[nb]===undefined){ dist[nb] = d+1; q.push(nb) }
  }
  const rings: Record<number, GraphNode[]> = {}
  g.nodes.forEach(n=>{ const d = (n.id===centerId)?0:(dist[n.id]??2); (rings[d] ||= []).push(n) })
  const ringGap = Math.min(w,h)/6
  Object.entries(rings).forEach(([k, arr])=>{
    const ring = parseInt(k,10)
    if(ring===0){ centerPos[centerId!] = {x: cx, y: cy}; return }
    const R = ring*ringGap
    const thetaStep = (Math.PI*2)/arr.length
    arr.forEach((n, i)=>{ centerPos[n.id] = { x: cx + R*Math.cos(i*thetaStep), y: cy + R*Math.sin(i*thetaStep) } })
  })
  return centerPos
}

function drawWeb(ctx: CanvasRenderingContext2D, cx:number, cy:number, maxR:number){
  ctx.save()
  ctx.strokeStyle = 'rgba(100,110,120,0.25)'
  for(let r=maxR/3; r<=maxR; r+=maxR/3){ ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI*2); ctx.stroke() }
  for(let i=0;i<12;i++){ const a = (Math.PI*2)*i/12; ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+maxR*Math.cos(a), cy+maxR*Math.sin(a)); ctx.stroke() }
  ctx.restore()
}

function edgeStyle(ctx: CanvasRenderingContext2D, kind: EdgeKind, t:number){
  ctx.setLineDash([]); ctx.lineWidth = 1.25; ctx.globalAlpha = 0.9
  if(kind==='hypothesis'){ ctx.setLineDash([8,8]); ctx.globalAlpha = 0.7 }
  if(kind==='active'){
    ctx.setLineDash([10,10]); ctx.lineDashOffset = (t*60)%20; ctx.globalAlpha = 0.85
  }
}

function drawGraph(ctx: CanvasRenderingContext2D, g: GraphSnapshot, pos: Record<string,{x:number,y:number}>, t:number, dpr:number){
  ctx.save()
  const allR = Object.values(pos).map(_=>0)
  // find bounds radius to draw web
  const w = ctx.canvas.width/dpr, h = ctx.canvas.height/dpr
  const cx = w/2, cy = h/2
  const maxR = Math.min(w,h)/2 - 20
  drawWeb(ctx, cx, cy, maxR)
  // Edges first
  g.edges.forEach(e=>{
    const a = pos[e.source], b = pos[e.target]
    if(!a||!b) return
    ctx.beginPath(); edgeStyle(ctx, e.kind, t)
    ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.strokeStyle = 'rgba(120,140,160,0.6)'; ctx.stroke()
  })
  // Nodes
  g.nodes.forEach(n=>{
    const p = pos[n.id]; if(!p) return
    const r = nodeRadius(n)
    ctx.beginPath(); ctx.fillStyle = COLORS[n.risk] || COLORS.gray; ctx.strokeStyle = 'rgba(60,68,76,0.9)'
    ctx.arc(p.x, p.y, r, 0, Math.PI*2); ctx.fill(); ctx.lineWidth = 1; ctx.stroke()
  })
  ctx.restore()
}

export type Selection = { node?: GraphNode|null }

type Props = { data?: GraphSnapshot, onSelect?: (n: GraphNode|null)=>void }

export default function GraphCanvas({data, onSelect}: Props){
  const ref = useRef<HTMLCanvasElement>(null)
  const [vp, setVp] = useState<Viewport>({x:0,y:0,k:1})
  const [hoverId, setHoverId] = useState<string|null>(null)
  const [animate, setAnimate] = useState<boolean>(false)
  const [layout, setLayout] = useState<Record<string,{x:number,y:number}>>({})

  // Resize and DPR handling
  useEffect(()=>{
    const cvs = ref.current; if(!cvs) return
    const ro = new ResizeObserver(()=>{
      const dpr = window.devicePixelRatio || 1
      const rect = cvs.getBoundingClientRect()
      cvs.width = Math.round(rect.width * dpr)
      cvs.height = Math.round(rect.height * dpr)
      const ctx = cvs.getContext('2d')!
      ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,cvs.width,cvs.height)
      if(data){ setLayout(computeLayout(data, rect.width, rect.height)) }
      draw()
    })
    ro.observe(cvs)
    return ()=> ro.disconnect()
  }, [data])

  // Determine if we need animation (active edges)
  useEffect(()=>{ setAnimate(!!data?.edges.some(e=> e.kind==='active')) }, [data])

  function draw(){
    const cvs = ref.current; if(!cvs || !data) return
    const ctx = cvs.getContext('2d')!
    const dpr = window.devicePixelRatio || 1
    const rect = cvs.getBoundingClientRect()
    // Clear
    ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,cvs.width,cvs.height)
    // Apply world transform
    applyTransform(ctx, vp)
    // Time
    const t = performance.now()/1000
    drawGraph(ctx, data, layout, t, dpr)
    // Hover ring
    if(hoverId){ const p = layout[hoverId]; if(p){ ctx.save(); ctx.beginPath(); ctx.strokeStyle='#a9c4e0'; ctx.lineWidth=2; ctx.arc(p.x,p.y, nodeRadius(data.nodes.find(n=>n.id===hoverId)!) + 4, 0, Math.PI*2); ctx.stroke(); ctx.restore() } }
  }

  // RAF loop if animate; otherwise draw only on demand
  useEffect(()=>{
    let raf = 0
    function loop(){ draw(); if(animate) raf = requestAnimationFrame(loop) }
    draw(); if(animate) raf = requestAnimationFrame(loop)
    return ()=> cancelAnimationFrame(raf)
  }, [vp, layout, animate, data, hoverId])

  // Hit test helper
  function pick(sx:number, sy:number){
    if(!data) return null
    const {x, y} = screenToWorld(vp, sx, sy)
    for(const n of data.nodes){ const p = layout[n.id]; if(!p) continue; const r = nodeRadius(n); const dx=x-p.x, dy=y-p.y; const d2 = (dx*dx)+(dy*dy); if(d2 <= r*r) return n }
    return null
  }

  // Pointer and touch interactions
  useEffect(()=>{
    const cvs = ref.current; if(!cvs) return
    let dragging=false, lastX=0, lastY=0
    let pinch=false, lastD=0

    function onPointerDown(e: PointerEvent){ dragging = true; lastX = e.clientX; lastY = e.clientY; (e.target as any).setPointerCapture(e.pointerId) }
    function onPointerMove(e: PointerEvent){ if(!dragging) return; const dx=e.clientX-lastX, dy=e.clientY-lastY; lastX=e.clientX; lastY=e.clientY; setVp(v=> ({...v, x: v.x+dx, y: v.y+dy})) }
    function onPointerUp(e: PointerEvent){ dragging=false }
    function onClick(e: MouseEvent){ if(!data) return; const n = pick(e.clientX, e.clientY); setHoverId(n?.id||null); onSelect && onSelect(n) }
    function onMouseMove(e: MouseEvent){ const n = pick(e.clientX, e.clientY); setHoverId(n?.id||null) }
    function onWheel(e: WheelEvent){ e.preventDefault(); const factor = Math.exp(-e.deltaY*0.001); const rect = cvs.getBoundingClientRect(); const sx=e.clientX-rect.left, sy=e.clientY-rect.top; const wx=(sx - vp.x)/vp.k, wy=(sy - vp.y)/vp.k; const nk = Math.min(3, Math.max(0.4, vp.k*factor)); const nx = sx - wx*nk, ny = sy - wy*nk; setVp({x:nx,y:ny,k:nk}) }

    // Touch pinch-zoom
    function onTouchStart(ev: TouchEvent){ if(ev.touches.length===2){ pinch=true; const [a,b]=[ev.touches[0], ev.touches[1]]; lastD = Math.hypot(a.clientX-b.clientX, a.clientY-b.clientY) } }
    function onTouchMove(ev: TouchEvent){ if(pinch && ev.touches.length===2){ ev.preventDefault(); const [a,b]=[ev.touches[0], ev.touches[1]]; const d = Math.hypot(a.clientX-b.clientX, a.clientY-b.clientY); const factor = d/Math.max(1,lastD); lastD = d; const rect = cvs.getBoundingClientRect(); const sx=(a.clientX+b.clientX)/2-rect.left, sy=(a.clientY+b.clientY)/2-rect.top; const wx=(sx - vp.x)/vp.k, wy=(sy - vp.y)/vp.k; const nk = Math.min(3, Math.max(0.4, vp.k*factor)); const nx = sx - wx*nk, ny = sy - wy*nk; setVp({x:nx,y:ny,k:nk}) } }
    function onTouchEnd(){ pinch=false }

    cvs.addEventListener('pointerdown', onPointerDown)
    cvs.addEventListener('pointermove', onPointerMove)
    cvs.addEventListener('pointerup', onPointerUp)
    cvs.addEventListener('click', onClick)
    cvs.addEventListener('mousemove', onMouseMove)
    cvs.addEventListener('wheel', onWheel, {passive:false})
    cvs.addEventListener('touchstart', onTouchStart, {passive:false})
    cvs.addEventListener('touchmove', onTouchMove, {passive:false})
    cvs.addEventListener('touchend', onTouchEnd)
    return ()=>{
      cvs.removeEventListener('pointerdown', onPointerDown)
      cvs.removeEventListener('pointermove', onPointerMove)
      cvs.removeEventListener('pointerup', onPointerUp)
      cvs.removeEventListener('click', onClick)
      cvs.removeEventListener('mousemove', onMouseMove)
      cvs.removeEventListener('wheel', onWheel)
      cvs.removeEventListener('touchstart', onTouchStart)
      cvs.removeEventListener('touchmove', onTouchMove)
      cvs.removeEventListener('touchend', onTouchEnd)
    }
  }, [data, vp, layout])

  // DevicePixelRatio redraw on change
  useEffect(()=>{ const h = ()=> draw(); window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', h); return ()=> window.matchMedia('(prefers-reduced-motion: reduce)').removeEventListener('change', h) }, [])

  return <canvas ref={ref} className='arsenal-canvas' aria-label='Attack graph canvas' />
}
