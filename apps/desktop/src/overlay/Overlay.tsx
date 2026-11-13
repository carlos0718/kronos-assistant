import { useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { STATE_LABEL, useEngine } from "../useEngine";
import { Orb } from "./Orb";
import "./Overlay.css";

// Tiempo que el overlay queda visible después de volver a inactivo.
const HIDE_AFTER_IDLE_MS = 2500;
// Si no hay motor, el aviso de error queda un poco más antes de ocultarse.
const HIDE_AFTER_ERROR_MS = 5000;
// Duración de la animación de salida (coincide con Overlay.css).
const LEAVE_MS = 250;

export function Overlay() {
  const { state, transcript, reply, error, send } = useEngine();
  const [leaving, setLeaving] = useState(false);
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
      send(stateRef.current === "idle" ? "activate" : "cancel");
    });
    return () => {
      unlisten.then((stop) => stop());
    };
  }, [send]);

  // Se oculta solo cuando no queda nada que mostrar.
  useEffect(() => {
    if (state !== "idle" && state !== "disconnected") {
      setLeaving(false);
      return;
    }
    const wait = state === "idle" ? HIDE_AFTER_IDLE_MS : HIDE_AFTER_ERROR_MS;
    const fade = setTimeout(() => setLeaving(true), wait);
    const hide = setTimeout(() => invoke("hide_overlay"), wait + LEAVE_MS);
    return () => {
      clearTimeout(fade);
      clearTimeout(hide);
    };
    // `summons` reinicia la cuenta si se lo invoca sin que cambie el estado.
  }, [state, summons]);

  const hasText = Boolean(transcript || reply || error);

  return (
    <main className="overlay" data-leaving={leaving}>
      {hasText && (
        <section className="bubble" aria-live="polite">
          {transcript && <p className="bubble-user">“{transcript}”</p>}
          {reply && <p className="bubble-reply">{reply}</p>}
          {error && <p className="bubble-error">{error}</p>}
        </section>
      )}
      <Orb state={state} size={104} />
      <p className="overlay-state">{STATE_LABEL[state]}</p>
    </main>
  );
}
