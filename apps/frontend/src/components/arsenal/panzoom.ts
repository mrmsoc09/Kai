
export type Viewport = { x: number; y: number; k: number }
export function applyTransform(ctx: CanvasRenderingContext2D, vp: Viewport){
  ctx.setTransform(vp.k, 0, 0, vp.k, vp.x, vp.y)
}
export function screenToWorld(vp: Viewport, sx: number, sy: number){
  return { x: (sx - vp.x)/vp.k, y: (sy - vp.y)/vp.k }
}
