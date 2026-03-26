/**
 * WebSocket hook for Kaison Orchestration chat streaming
 * Handles real-time message streaming and approval workflows.
 *
 * Orchestration is handled by Gemini CLI. See orchestration/gemini_orchestrator.py.
 * The default WebSocket URL is controlled by the K1_ORCHESTRATION_WS_URL env variable.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
  toolCalls?: ToolCall[];
  approvalRequired?: boolean;
  approvalId?: string;
}

export interface ToolCall {
  tool: string;
  params: Record<string, any>;
  description?: string;
  tier?: number;
}

export interface ApprovalRequest {
  approvalId: string;
  operation: string;
  tier: number;
  details: Record<string, any>;
  message: string;
}

export interface StreamEvent {
  type: string;
  content?: string;
  message?: ChatMessage;
  data?: any;
  timestamp?: string;
}

interface UseOrchestrationStreamOptions {
  apiUrl?: string;
  sessionId?: string;
  onMessage?: (message: ChatMessage) => void;
  onToken?: (token: string) => void;
  onToolCall?: (toolCall: ToolCall) => void;
  onApprovalRequired?: (approval: ApprovalRequest) => void;
  onError?: (error: Error) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
}

interface UseOrchestrationStreamReturn {
  isConnected: boolean;
  isStreaming: boolean;
  sessionId: string | null;
  messages: ChatMessage[];
  pendingApprovals: ApprovalRequest[];
  streamingContent: string;
  sendMessage: (content: string, context?: Record<string, any>) => void;
  approveRequest: (approvalId: string) => void;
  rejectRequest: (approvalId: string, reason?: string) => void;
  connect: () => void;
  disconnect: () => void;
  clearHistory: () => void;
}

export function useOrchestrationStream(
  options: UseOrchestrationStreamOptions = {},
): UseOrchestrationStreamReturn {
  // K1_ORCHESTRATION_WS_URL is injected at build time via VITE_K1_ORCHESTRATION_WS_URL
  const envWsUrl = typeof window !== 'undefined'
    ? (import.meta as any).env?.VITE_K1_ORCHESTRATION_WS_URL
    : undefined;
  const defaultApiUrl = envWsUrl
    ?? (typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/orchestration/ws/chat`
      : 'ws://localhost:8000/api/v1/orchestration/ws/chat');

  const {
    apiUrl = defaultApiUrl,
    sessionId: initialSessionId,
    onMessage,
    onToken,
    onToolCall,
    onApprovalRequired,
    onError,
    autoReconnect = true,
    reconnectInterval = 3000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(initialSessionId || null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalRequest[]>([]);
  const [streamingContent, setStreamingContent] = useState('');

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatRef = useRef<NodeJS.Timeout | null>(null);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const url = initialSessionId ? `${apiUrl}?session_id=${initialSessionId}` : apiUrl;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('[Orchestration] WebSocket connected');

      // Start heartbeat
      heartbeatRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);
        handleStreamEvent(data);
      } catch (error) {
        console.error('[Orchestration] Failed to parse message:', error);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsStreaming(false);
      console.log('[Orchestration] WebSocket disconnected');

      if (heartbeatRef.current) {
        clearInterval(heartbeatRef.current);
      }

      // Auto-reconnect
      if (autoReconnect) {
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('[Orchestration] Attempting to reconnect...');
          connect();
        }, reconnectInterval);
      }
    };

    ws.onerror = (error) => {
      console.error('[Orchestration] WebSocket error:', error);
      onError?.(new Error('WebSocket connection error'));
    };
  }, [apiUrl, initialSessionId, autoReconnect, reconnectInterval, onError]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // Handle incoming stream events
  const handleStreamEvent = useCallback(
    (event: StreamEvent) => {
      switch (event.type) {
        case 'session_started':
          setSessionId(event.data?.session_id || event.timestamp);
          break;

        case 'message_received':
          // User message was received by server
          break;

        case 'token':
          // Streaming token
          setIsStreaming(true);
          setStreamingContent((prev) => prev + (event.content || ''));
          onToken?.(event.content || '');
          break;

        case 'message_complete': {
          // Assistant message complete
          setIsStreaming(false);
          const assistantMessage = event.message || {
            id: Date.now().toString(),
            role: 'assistant' as const,
            content: streamingContent,
            timestamp: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMessage]);
          setStreamingContent('');
          onMessage?.(assistantMessage);
          break;
        }

        case 'tool_call': {
          const toolCall: ToolCall = {
            tool: event.data?.tool || '',
            params: event.data?.params || {},
            description: event.data?.description,
            tier: event.data?.tier,
          };
          onToolCall?.(toolCall);
          break;
        }

        case 'tool_result': {
          // Tool execution result
          const toolResultMessage: ChatMessage = {
            id: Date.now().toString(),
            role: 'tool',
            content: JSON.stringify(event.data?.result || event.data, null, 2),
            timestamp: new Date().toISOString(),
            metadata: { tool: event.data?.tool },
          };
          setMessages((prev) => [...prev, toolResultMessage]);
          break;
        }

        case 'approval_required': {
          const approval: ApprovalRequest = {
            approvalId: event.data?.approval_id || '',
            operation: event.data?.operation || '',
            tier: event.data?.tier || 0,
            details: event.data?.details || {},
            message: event.data?.message || 'Approval required',
          };
          setPendingApprovals((prev) => [...prev, approval]);
          onApprovalRequired?.(approval);
          break;
        }

        case 'approval_granted':
        case 'approval_rejected':
          setPendingApprovals((prev) =>
            prev.filter((a) => a.approvalId !== event.data?.approval_id),
          );
          break;

        case 'history':
          // Received chat history
          setMessages(event.data?.messages || []);
          break;

        case 'error':
          console.error('[Orchestration] Server error:', event.data?.message);
          onError?.(new Error(event.data?.message || 'Server error'));
          break;

        case 'pong':
          // Heartbeat response
          break;

        default:
          console.log('[Orchestration] Unknown event type:', event.type);
      }
    },
    [streamingContent, onToken, onMessage, onToolCall, onApprovalRequired, onError],
  );

  // Send a message
  const sendMessage = useCallback((content: string, context?: Record<string, any>) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[Orchestration] WebSocket not connected');
      return;
    }

    // Add user message to local state
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    // Reset streaming content
    setStreamingContent('');

    // Send to server
    wsRef.current.send(
      JSON.stringify({
        type: 'message',
        content,
        context,
      }),
    );
  }, []);

  // Approve a pending request
  const approveRequest = useCallback((approvalId: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[Orchestration] WebSocket not connected');
      return;
    }

    wsRef.current.send(
      JSON.stringify({
        type: 'approval_response',
        approval_id: approvalId,
        decision: 'approved',
      }),
    );
  }, []);

  // Reject a pending request
  const rejectRequest = useCallback((approvalId: string, reason?: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('[Orchestration] WebSocket not connected');
      return;
    }

    wsRef.current.send(
      JSON.stringify({
        type: 'approval_response',
        approval_id: approvalId,
        decision: 'rejected',
        reason: reason || 'User rejected',
      }),
    );
  }, []);

  // Clear chat history
  const clearHistory = useCallback(() => {
    setMessages([]);
    setPendingApprovals([]);
    setStreamingContent('');
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return {
    isConnected,
    isStreaming,
    sessionId,
    messages,
    pendingApprovals,
    streamingContent,
    sendMessage,
    approveRequest,
    rejectRequest,
    connect,
    disconnect,
    clearHistory,
  };
}

export default useOrchestrationStream;
