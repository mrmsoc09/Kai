/**
 * useChatStream Hook
 * WebSocket hook for real-time chat messages
 */

import { useEffect, useRef, useState } from 'react'
import { ChatMessage } from '../api/orchestrator'

export function useChatStream() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    const wsUrl = `${
      window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    }//${window.location.host}/orchestrator/ws/chat`

    try {
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        setConnected(true)
        setError(null)
      }

      ws.current.onmessage = (event) => {
        try {
          const message: ChatMessage = JSON.parse(event.data)
          setMessages((prev) => [...prev, message])
        } catch {
          // Ignore malformed messages
        }
      }

      ws.current.onerror = () => {
        setError('WebSocket connection failed')
        setConnected(false)
      }

      ws.current.onclose = () => {
        setConnected(false)
      }
    } catch (err) {
      setError('Could not connect to chat stream')
    }

    return () => {
      ws.current?.close()
    }
  }, [])

  const send = (message: string) => {
    if (ws.current && connected) {
      ws.current.send(JSON.stringify({ message }))
    }
  }

  return { messages, connected, send, error }
}
