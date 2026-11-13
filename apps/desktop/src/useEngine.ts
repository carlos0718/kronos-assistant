import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";

// Estados del asistente, según el protocolo motor ↔ interfaz.
export type AssistantState = "disconnected" | "idle" | "listening" | "thinking" | "speaking";

export const STATE_LABEL: Record<AssistantState, string> = {
  disconnected: "Motor sin conectar",
  idle: "Inactivo",
  listening: "Escuchando",
  thinking: "Pensando",
  speaking: "Hablando",
};

const PROTOCOL_VERSION = 1;

// Lo que informa la parte Rust de la app sobre el proceso del motor.
type EngineStatus =
  | { status: "starting" }
  | { status: "ready"; port: number; token: string }
  | { status: "failed"; message: string };

type EngineMessage = { v: number; type: string; payload: Record<string, unknown> };

export function useEngine() {
  const [state, setState] = useState<AssistantState>("disconnected");
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let disposed = false;

    function handle(message: EngineMessage) {
      if (message.v !== PROTOCOL_VERSION) {
        setError(`Versión de protocolo no compatible: ${message.v}`);
        return;
      }
      const { payload } = message;
      switch (message.type) {
        case "state_changed": {
          const next = payload.state as AssistantState;
          setError(null);
          setState(next);
          // Cada vez que empieza a escuchar arranca un intercambio nuevo.
          if (next === "listening") {
            setTranscript("");
            setReply("");
          }
          break;
        }
        case "transcript_partial":
        case "transcript_final":
          setTranscript(String(payload.text ?? ""));
          break;
        case "assistant_delta":
          setReply((current) => current + String(payload.text ?? ""));
          break;
        case "error":
          setError(String(payload.message ?? "Error del motor."));
          break;
      }
    }

    function connect(port: number, token: string) {
      if (disposed || socketRef.current) return;
      const socket = new WebSocket(`ws://127.0.0.1:${port}/ws?token=${encodeURIComponent(token)}`);
      socketRef.current = socket;

      socket.onmessage = (event) => handle(JSON.parse(event.data) as EngineMessage);
      socket.onerror = () => {
        if (!disposed) setError("No se pudo conectar con el motor.");
      };
      socket.onclose = () => {
        if (socketRef.current === socket) socketRef.current = null;
        if (!disposed) setState("disconnected");
      };
    }

    function apply(status: EngineStatus) {
      if (disposed) return;
      if (status.status === "ready") connect(status.port, status.token);
      if (status.status === "failed") {
        setError(status.message);
        setState("disconnected");
      }
    }

    // Primero se escucha y después se consulta, para no perder el aviso.
    const unlisten = listen<EngineStatus>("engine:status", (event) => apply(event.payload));
    invoke<EngineStatus>("engine_status")
      .then(apply)
      .catch((e) => !disposed && setError(`No se pudo consultar el motor: ${e}`));

    return () => {
      disposed = true;
      unlisten.then((stop) => stop());
      socketRef.current?.close();
      socketRef.current = null;
    };
  }, []);

  /** Envía un mensaje al motor. Devuelve false si no hay conexión. */
  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    const socket = socketRef.current;
    if (socket?.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify({ v: PROTOCOL_VERSION, type, payload }));
    return true;
  }, []);

  return { state, transcript, reply, error, send };
}
