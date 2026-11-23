import { invoke } from "@tauri-apps/api/core";
import { type FormEvent, useEffect, useRef, useState } from "react";
import type { SecretRequest } from "../engine/useEngine";
import "./Confirm.css";
import "./SecretPrompt.css";

type Props = {
  request: SecretRequest;
  /** `null` es cancelar. */
  onSubmit: (secret: string | null) => void;
};

/**
 * El pedido de la clave secreta antes de una acción crítica. Se escribe acá:
 * no se dicta, para que no quede en la transcripción ni la oiga nadie.
 */
export function SecretPrompt({ request, onSubmit }: Props) {
  const [secret, setSecret] = useState("");
  const input = useRef<HTMLInputElement>(null);

  // El overlay no recibe el teclado de fábrica: mientras se pide la clave, sí.
  useEffect(() => {
    invoke("focus_overlay", { focus: true })
      .then(() => input.current?.focus())
      .catch(() => {});
    return () => {
      invoke("focus_overlay", { focus: false }).catch(() => {});
    };
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (secret) onSubmit(secret);
  }

  return (
    <form className="confirm secret" onSubmit={submit}>
      <p className="confirm-question">Escribí tu clave secreta para {request.summary}.</p>
      {request.detail && <code className="confirm-detail">{request.detail}</code>}
      <input
        ref={input}
        type="password"
        className="secret-input"
        aria-label="Clave secreta"
        autoComplete="off"
        spellCheck={false}
        value={secret}
        onChange={(event) => setSecret(event.target.value)}
      />
      <div className="confirm-actions">
        <button type="button" className="confirm-no" onClick={() => onSubmit(null)}>
          Cancelar
        </button>
        <button type="submit" className="confirm-yes" disabled={!secret}>
          Autorizar
        </button>
      </div>
      <p className="confirm-hint">La clave no se dicta: se escribe y no la ve el modelo.</p>
    </form>
  );
}
