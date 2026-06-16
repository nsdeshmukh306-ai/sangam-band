import { useCallback, useEffect, useRef, useState } from "react";
import { WS_BASE } from "../api";

export type WsReadyState = "idle" | "connecting" | "open" | "reconnecting" | "closed";

interface Opts {
  maxRetries?: number;
  initialDelayMs?: number;
  onMessage: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

/**
 * WebSocket hook with exponential-backoff reconnect.
 *
 * Solves the "silent-deaf-agent" problem: if the Band WS connection between
 * the frontend and the backend drops (e.g. network hiccup, Vite HMR reload,
 * container restart), the hook automatically reconnects up to maxRetries
 * times before giving up and switching to HTTP fallback.
 *
 * Callers pass a nullable path — set it to null to keep the socket closed,
 * and to a non-null path to open / reopen the connection.
 */
export function useReconnectingWs(path: string | null, opts: Opts) {
  const { maxRetries = 6, initialDelayMs = 800, onMessage, onOpen, onClose } = opts;

  const [readyState, setReadyState] = useState<WsReadyState>("idle");
  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const abortedRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep latest callbacks stable without causing reconnects
  const cbRef = useRef({ onMessage, onOpen, onClose });
  cbRef.current = { onMessage, onOpen, onClose };

  const cleanup = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.close(1000, "cleanup");
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback((p: string) => {
    if (abortedRef.current) return;
    setReadyState("connecting");

    const url = `${WS_BASE}${p}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (abortedRef.current) { ws.close(); return; }
      retriesRef.current = 0;
      setReadyState("open");
      cbRef.current.onOpen?.();
    };

    ws.onmessage = (e) => {
      try { cbRef.current.onMessage(JSON.parse(e.data as string)); } catch { /* ignore */ }
    };

    ws.onerror = () => { ws.close(); };

    ws.onclose = (ev) => {
      wsRef.current = null;
      if (abortedRef.current || ev.wasClean) {
        setReadyState("closed");
        cbRef.current.onClose?.();
        return;
      }
      if (retriesRef.current >= maxRetries) {
        setReadyState("closed");
        cbRef.current.onClose?.();
        return;
      }
      retriesRef.current++;
      const delay = initialDelayMs * Math.pow(2, retriesRef.current - 1);
      setReadyState("reconnecting");
      timerRef.current = setTimeout(() => connect(p), delay);
    };
  }, [maxRetries, initialDelayMs, cleanup]);

  useEffect(() => {
    if (!path) {
      abortedRef.current = false;
      retriesRef.current = 0;
      setReadyState("idle");
      return;
    }
    abortedRef.current = false;
    retriesRef.current = 0;
    connect(path);
    return () => {
      abortedRef.current = true;
      cleanup();
    };
  }, [path, connect, cleanup]);

  const closeManually = useCallback(() => {
    abortedRef.current = true;
    cleanup();
    setReadyState("closed");
  }, [cleanup]);

  return { readyState, close: closeManually };
}
