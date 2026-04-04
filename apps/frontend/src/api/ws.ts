
export function connectWS(token?: string){
  const base = window.location.origin.replace('http', 'ws')
  const query = token ? `?token=${encodeURIComponent(token)}` : ''
  const url = `${base}/ws${query}`
  const ws = new WebSocket(url)
  return ws
}
