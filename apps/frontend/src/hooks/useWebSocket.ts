/**
 * useWebSocket Hook
 *
 * Reusable hook for managing WebSocket connections with automatic reconnection,
 * connection status tracking, and message handling.
 */

import { useEffect, useRef, useCallback, useState } from 'react';

interface UseWebSocketOptions {
  shouldReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

const DEFAULT_OPTIONS: UseWebSocketOptions = {
  shouldReconnect: true,
  reconnectInterval: 3000,
  maxReconnectAttempts: 5,
};

export const useWebSocket = (
  url: string | null,
  onMessage: (message: string) => void,
  options: UseWebSocketOptions = {}
) => {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mergedOptions = { ...DEFAULT_OPTIONS, ...options };

  const connect = useCallback(() => {
    // Skip if already connecting or url is null
    if (!url || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log(`[WebSocket] Connected to ${url}`);
        setConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0;

        // Send initial ping to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          } else {
            clearInterval(pingInterval);
          }
        }, 30000); // Ping every 30 seconds
      };

      ws.onmessage = (event) => {
        try {
          onMessage(event.data);
        } catch (err) {
          console.error('[WebSocket] Message handler error:', err);
          setError('Failed to process message');
        }
      };

      ws.onerror = (event) => {
        console.error('[WebSocket] Error:', event);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log(`[WebSocket] Disconnected from ${url}`);
        setConnected(false);
        wsRef.current = null;

        // Attempt reconnection
        if (mergedOptions.shouldReconnect && reconnectAttemptsRef.current < (mergedOptions.maxReconnectAttempts || 5)) {
          reconnectAttemptsRef.current += 1;
          const delay = (mergedOptions.reconnectInterval || 3000) * reconnectAttemptsRef.current;
          console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttemptsRef.current >= (mergedOptions.maxReconnectAttempts || 5)) {
          setError('Max reconnection attempts reached');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[WebSocket] Connection error:', err);
      setError(`Failed to connect: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [url, onMessage, mergedOptions]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnected(false);
  }, []);

  const sendMessage = useCallback(
    (message: string | Record<string, any>) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn('[WebSocket] Cannot send message: WebSocket not connected');
        setError('WebSocket not connected');
        return;
      }

      try {
        const payload = typeof message === 'string' ? message : JSON.stringify(message);
        wsRef.current.send(payload);
      } catch (err) {
        console.error('[WebSocket] Send error:', err);
        setError(`Failed to send message: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
    },
    []
  );

  // Establish connection on mount, cleanup on unmount
  useEffect(() => {
    if (!url) return;

    connect();

    return () => {
      disconnect();
    };
  }, [url, connect, disconnect]);

  return {
    connected,
    error,
    sendMessage,
    disconnect,
    ws: wsRef.current,
  };
};
