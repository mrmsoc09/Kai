import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppStore } from '../store/appStore';
import { appConfig } from '../utils/config';
import type { MissionEventMessage } from '../types';

interface UseWebSocketOptions<TMessage> {
  path?: string;
  reconnectAttempts?: number;
  reconnectDelayMs?: number;
  onMessage?: (message: TMessage) => void;
}

const buildWebSocketUrl = (path: string): string => {
  const base = appConfig.webSocketBaseUrl;
  const token = useAppStore.getState().auth.token;
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;

  let url: URL;

  if (base.startsWith('ws://') || base.startsWith('wss://')) {
    const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base;
    const candidate = path ? `${normalizedBase}${normalizedPath}` : normalizedBase;
    url = new URL(candidate);
  } else {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const normalizedBase = base.startsWith('/') ? base : `/${base}`;
    const candidate = path ? `${normalizedBase}${normalizedPath}` : normalizedBase;
    url = new URL(`${protocol}//${window.location.host}${candidate}`);
  }

  if (token) {
    url.searchParams.set('token', token);
  }

  return url.toString();
};

export function useWebSocket<TMessage = MissionEventMessage>(options: UseWebSocketOptions<TMessage> = {}) {
  const { path = '', reconnectAttempts = 5, reconnectDelayMs = 1500, onMessage } = options;
  const setWebSocketState = useAppStore((state) => state.setWebSocketState);
  const [lastMessage, setLastMessage] = useState<TMessage | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const reconnectCountRef = useRef(0);
  const manualCloseRef = useRef(false);

  const clearReconnectTimer = () => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  };

  const disconnect = useCallback(() => {
    manualCloseRef.current = true;
    clearReconnectTimer();

    if (socketRef.current && socketRef.current.readyState !== WebSocket.CLOSED) {
      socketRef.current.close();
    }

    socketRef.current = null;
    setWebSocketState('disconnected');
  }, [setWebSocketState]);

  const connect = useCallback(() => {
    const token = useAppStore.getState().auth.token;
    if (!token) {
      setWebSocketState('disconnected');
      return;
    }

    manualCloseRef.current = false;
    clearReconnectTimer();
    setWebSocketState('connecting');

    try {
      const socket = new WebSocket(buildWebSocketUrl(path));
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectCountRef.current = 0;
        setWebSocketState('connected');
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as TMessage;
          setLastMessage(payload);
          onMessage?.(payload);
        } catch {
          // Ignore malformed non-JSON frames to keep stream resilient.
        }
      };

      socket.onerror = () => {
        setWebSocketState('error');
      };

      socket.onclose = () => {
        if (manualCloseRef.current) {
          return;
        }

        if (reconnectCountRef.current >= reconnectAttempts) {
          setWebSocketState('disconnected');
          return;
        }

        reconnectCountRef.current += 1;
        setWebSocketState('connecting');

        reconnectTimerRef.current = window.setTimeout(() => {
          connect();
        }, reconnectDelayMs);
      };
    } catch {
      setWebSocketState('error');
    }
  }, [onMessage, path, reconnectAttempts, reconnectDelayMs, setWebSocketState]);

  const sendMessage = useCallback((message: Record<string, unknown>) => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) {
      return false;
    }

    socketRef.current.send(JSON.stringify(message));
    return true;
  }, []);

  const subscribe = useCallback(
    (channel: string, missionId?: string) =>
      sendMessage({
        action: 'subscribe',
        channel,
        mission_id: missionId,
      }),
    [sendMessage],
  );

  const unsubscribe = useCallback(
    (channel: string, missionId?: string) =>
      sendMessage({
        action: 'unsubscribe',
        channel,
        mission_id: missionId,
      }),
    [sendMessage],
  );

  const subscribeToMission = useCallback((missionId: string) => subscribe('mission_events', missionId), [subscribe]);

  useEffect(() => disconnect, [disconnect]);

  return {
    connect,
    disconnect,
    sendMessage,
    subscribe,
    unsubscribe,
    subscribeToMission,
    lastMessage,
  };
}
