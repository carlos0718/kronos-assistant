import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useEffect, useRef, useState } from "react";
import { STATE_LABEL, useEngine } from "../engine/useEngine";
import { Orb } from "../shared/Orb";
import { useChatShown } from "../shared/useChatShown";
import { Confirm } from "./Confirm";
import { SecretPrompt } from "./SecretPrompt";
import "./Overlay.css";

// Tiempo que el overlay queda visible después de volver a inactivo: da para
// leer la respuesta, también después de una despedida.
const HIDE_AFTER_IDLE_MS = 5000;
// Si no hay motor, el aviso de error queda lo mismo antes de ocultarse.
const HIDE_AFTER_ERROR_MS = 5000;
// Duración de la animación de salida (coincide con Overlay.css).
const LEAVE_MS = 250;

export function Overlay() {
  const { state, transcript, reply, error, confirmation, secretRequest, send, clear } = useEngine();
  const [leaving, setLeaving] = useState(false);
  const [chatShown, setChatShown] = useChatShown();
  const [summons, setSummons] = useState(0);
  // El aviso de invocación llega por un evento: se lee el estado más reciente sin volver a suscribirse.
  const stateRef = useRef(state);
  stateRef.current = state;

  // El usuario invocó a Kronos (atajo o bandeja): si estaba inactivo empieza
  // a escuchar; si estaba haciendo algo, lo corta.
  useEffect(() => {
    const unlisten = listen("overlay:summon", () => {
      setLeaving(false);
      setSummons((count) => count + 1);
      if (stateRef.current === "idle") {
        clear();
        send("activate");
      } else {
        send("cancel");
      }
    });
    return () => {
      unlisten.then((stop) => stop());
    };
  }, [send, clear]);

  // Kronos también empieza por su cuenta, al oír su nombre: el overlay
  // aparece aunque nadie lo haya invocado con el atajo.
  const wasActive = useRef(false);
  useEffect(() => {
    const active = state !== "idle" && state !== "disconnected";
    if (active && !wasActive.current) invoke("show_overlay");
    wasActive.current = active;
  }, [state]);

  // Se oculta solo cuando no queda nada que mostrar.
  // biome-ignore lint/correctness/useExhaustiveDependencies: `summons` reinicia la cuenta si se lo invoca sin que cambie el estado.
  useEffect(() => {
    if (state !== "idle" && state !== "disconnected") {
      setLeaving(false);
      return;
    }
    const wait = state === "idle" ? HIDE_AFTER_IDLE_MS : HIDE_AFTER_ERROR_MS;
    const fade = setTimeout(() => setLeaving(true), wait);
    const hide = setTimeout(() => {
      invoke("hide_overlay");
      clear();
    }, wait + LEAVE_MS);
    return () => {
      clearTimeout(fade);
      clearTimeout(hide);
    };
  }, [state, summons, clear]);

  const said = Boolean(transcript || reply);
  // Con el texto oculto se siguen mostrando la pregunta para aprobar y los
  // errores: sin ellos el usuario no podría contestar ni sabría qué pasó.
  const hasText = (chatShown && said) || Boolean(error || confirmation || secretRequest);

  return (
    <main className="overlay" data-leaving={leaving}>
      {hasText && (
        <section className="bubble" aria-live="polite">
          {chatShown && transcript && <p className="bubble-user">“{transcript}”</p>}
          {/* Mientras hay algo que aprobar, la pregunta ocupa el lugar de la respuesta. */}
          {secretRequest ? (
            <SecretPrompt
              request={secretRequest}
              onSubmit={(secret) =>
                secret === null
                  ? send("secret_cancel", { id: secretRequest.id })
                  : send("secret", { id: secretRequest.id, value: secret })
              }
            />
          ) : confirmation ? (
            <Confirm
              confirmation={confirmation}
              onAnswer={(approved) => send(approved ? "confirm" : "deny", { id: confirmation.id })}
            />
          ) : (
            chatShown && reply && <p className="bubble-reply">{reply}</p>
          )}
          {error && <p className="bubble-error">{error}</p>}
        </section>
      )}
      <div className="overlay-orb">
        <Orb state={state} size={104} />
        <button
          type="button"
          className="chat-toggle"
          aria-pressed={chatShown}
          aria-label={chatShown ? "Ocultar el texto" : "Mostrar el texto"}
          title={chatShown ? "Ocultar el texto" : "Mostrar el texto"}
          data-waiting={!chatShown && said}
          onClick={() => setChatShown(!chatShown)}
        >
          <ChatIcon />
        </button>
      </div>
      <p className="overlay-state">{STATE_LABEL[state]}</p>
    </main>
  );
}

/** Una burbuja de diálogo, como las del chat. */
function ChatIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5h-7.5L7 20v-3.5H5A1.5 1.5 0 0 1 3.5 15V7A1.5 1.5 0 0 1 5 5.5z" />
    </svg>
  );
}
