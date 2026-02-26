
export function connectWS(token: string){
  const base = window.location.origin.replace('http', 'ws')
  const url = `${base}/ws?token=${encodeURIComponent(token)}`
  const ws = new WebSocket(url)
  return ws
}
