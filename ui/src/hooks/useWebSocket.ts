import { useEffect, useRef, useState, useCallback } from 'react'
import type { WebSocketMessage } from '@/types'

export function useWebSocket(url: string) {
  const ws = useRef<WebSocket | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  
  useEffect(() => {
    const socket = new WebSocket(url)
    ws.current = socket
    
    socket.onopen = () => {
      setIsConnected(true)
      console.log('WebSocket connected')
    }
    
    socket.onclose = () => {
      setIsConnected(false)
      console.log('WebSocket disconnected')
    }
    
    socket.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data)
        setLastMessage(message)
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }
    
    socket.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    return () => {
      socket.close()
    }
  }, [url])
  
  const sendMessage = useCallback((message: unknown) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message))
    }
  }, [])
  
  return { isConnected, lastMessage, sendMessage }
}
