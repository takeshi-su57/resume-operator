import { useCallback, useEffect, useRef, useState } from "react";

import type { ClientMessage, ServerMessage } from "@/lib/events";

import { serverWsUrl } from "./api";

export type WSStatus = "idle" | "connecting" | "open" | "closed" | "error";

type Options = {
  /** Called once per inbound message. */
  onMessage: (msg: ServerMessage) => void;
  /** Called when the socket transitions to a terminal state. */
  onClose?: (event: CloseEvent) => void;
};

/**
 * Tiny typed WebSocket hook for driving an interactive flow over
 * `/api/ws/run` or `/api/ws/bootstrap`. Lives outside any component
 * so the run-screen state machine can use it via composition.
 *
 * Lifecycle:
 *   1. `connect(path)` opens the socket and transitions to `connecting`.
 *   2. On `open`, callers `send(StartMessage)` to kick off the flow.
 *   3. Inbound messages flow through `onMessage`; client replies
 *      flow back via `send`.
 *   4. The socket closes itself when the server sends `done`/`error`.
 *      `disconnect()` does the same client-side.
 *
 * Reconnect is intentionally not wired — server-side flows are
 * stateful (mid-approval-loop), and a transparent reconnect would
 * silently re-run nodes. If the connection dies, the user sees an
 * error and explicitly retries.
 */
export function useFlowSocket({ onMessage, onClose }: Options) {
  const ref = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<WSStatus>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Stash the latest callbacks in a ref so the open/close handlers
  // capture the right ones across re-renders.
  const handlersRef = useRef({ onMessage, onClose });
  handlersRef.current = { onMessage, onClose };

  const connect = useCallback((path: string) => {
    if (ref.current) {
      ref.current.close();
    }
    setErrorMsg(null);
    setStatus("connecting");
    const socket = new WebSocket(serverWsUrl(path));
    ref.current = socket;
    socket.onopen = () => setStatus("open");
    socket.onclose = (ev) => {
      setStatus("closed");
      handlersRef.current.onClose?.(ev);
    };
    socket.onerror = () => {
      setStatus("error");
      setErrorMsg("WebSocket error");
    };
    socket.onmessage = (ev) => {
      try {
        const parsed = JSON.parse(ev.data) as ServerMessage;
        handlersRef.current.onMessage(parsed);
      } catch (err) {
        console.error("WS parse error", err, ev.data);
      }
    };
  }, []);

  const send = useCallback((msg: ClientMessage) => {
    const socket = ref.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      console.warn("WS send called while not OPEN", socket?.readyState);
      return;
    }
    socket.send(JSON.stringify(msg));
  }, []);

  const disconnect = useCallback(() => {
    ref.current?.close();
    ref.current = null;
  }, []);

  useEffect(() => {
    return () => {
      ref.current?.close();
      ref.current = null;
    };
  }, []);

  return { status, errorMsg, connect, send, disconnect } as const;
}
