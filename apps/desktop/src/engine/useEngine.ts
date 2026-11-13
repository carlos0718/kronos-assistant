import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useCallback, useEffect, useRef, useState } from "react";
import { type ClientMessage, type EngineState, PROTOCOL_VERSION, type ServerMessage } from "./protocol";

// Lo que muestra la interfaz: los estados del motor, más "sin conexión".
export type AssistantState = EngineState | "disconnected";

export const STATE_LABEL: Record<AssistantState, string> = {
  disconnected: "Motor sin conectar",
  idle: "Inactivo",
  listening: "Escuchando",
  thinking: "Pensando",
  speaking: "Hablando",
};

// Lo que informa la parte Rust de la app sobre el proceso del motor.
type EngineStatus =
  | { status: "starting" }
  | { status: "ready"; port: number; token: string }
  | { status: "failed"; message: string };

export function useEngine() {
  const [state, setState] = useState<AssistantState>("disconnected");
  const [transcript, setTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let disposed = false;

    function handle(message: ServerMessage) {
      if (message.v !== PROTOCOL_VERSION) {
        setError(`Versión de protocolo no compatible: ${message.v}`);
        return;
      }
      switch (message.type) {
        case "state_changed": {
          const next = message.payload.state;
          setError(null);
          setState(next);
          // Cada vez que empieza a escuchar arranca un intercambio nuevo.
          if (next === "listening") {
            setTranscript("");
            setReply("");
          }
          break;
        }
        case "transcript_final":
          setTranscript(message.payload.text);
          break;
        case "assistant_delta":
          setReply((current) => current + message.payload.text);
          break;
        case "error":
          setError(message.payload.message);
          break;
      }
    }

    function connect(port: number, token: string) {
      if (disposed || socketRef.current) return;
      const socket = new WebSocket(`ws://127.0.0.1:${port}/ws?token=${encodeURIComponent(token)}`);
      socketRef.current = socket;

      socket.onmessage = (event) => handle(JSON.parse(event.data) as ServerMessage);
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
  const send = useCallback((type: ClientMessage, payload: Record<string, unknown> = {}) => {
    const socket = socketRef.current;
    if (socket?.readyState !== WebSocket.OPEN) return false;
    socket.send(JSON.stringify({ v: PROTOCOL_VERSION, type, payload }));
    return true;
  }, []);

  return { state, transcript, reply, error, send };
}
