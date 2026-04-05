/**
 * useAgentStream Hook
 * WebSocket hook for real-time agent execution events
 */

import { useEffect, useRef, useState } from 'react'

export interface AgentEvent {
  type:
    | 'agent_started'
    | 'agent_complete'
    | 'finding_discovered'
    | 'phase_transition'
    | 'approval_required'
    | 'mission_complete'
    | 'error'
  tool_name?: string
  crew_agent?: string
  finding?: {
    type: string
    severity: string
    value: string
  }
  phase?: number
  mission_id: string
  timestamp: string
  data?: Record<string, any>
}

export function useAgentStream(missionId: string) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!missionId) return

    const wsUrl = `${
      window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    }//${window.location.host}/orchestrator/ws/agents`

    try {
      ws.current = new WebSocket(wsUrl)

      ws.current.onopen = () => {
        setConnected(true)
        setError(null)
        // Send mission subscription
        ws.current?.send(
          JSON.stringify({
            type: 'subscribe',
            mission_id: missionId,
          })
        )
      }

      ws.current.onmessage = (event) => {
        try {
          const agentEvent: AgentEvent = JSON.parse(event.data)
          setEvents((prev) => [agentEvent, ...prev])
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
      setError('Could not connect to agent stream')
    }

    return () => {
      ws.current?.close()
    }
  }, [missionId])

  return { events, connected, error }
}
