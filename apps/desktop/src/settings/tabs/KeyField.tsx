import { type ReactNode, useState } from "react";
import "./ProfileGroup.css";
import "./KeyField.css";

/**
 * Campo para pegar la clave de un servicio en la nube (Anthropic, ElevenLabs).
 * La clave se manda al motor y no vuelve: el campo solo sabe si hay una guardada.
 * `onSave` y `onDelete` devuelven si salió bien; si no, el error lo muestra la pestaña.
 */
export function KeyField({
  label,
  placeholder,
  hasKey,
  disabled,
  onSave,
  onDelete,
  children,
}: {
  label: string;
  placeholder: string;
  hasKey: boolean;
  disabled: boolean;
  onSave: (key: string) => Promise<boolean>;
  onDelete: () => Promise<boolean>;
  /** Qué pasa con la clave: dónde se guarda, a quién se le manda y quién cobra. */
  children: ReactNode;
}) {
  const [key, setKey] = useState("");

  async function save() {
    if (await onSave(key)) setKey("");
  }

  return (
    <div className="profile key-field">
      <label>
        <span>{label}</span>
        <input
          type="password"
          value={key}
          autoComplete="off"
          spellCheck={false}
          placeholder={hasKey ? "Ya hay una clave guardada" : placeholder}
          disabled={disabled}
          onChange={(event) => setKey(event.target.value)}
        />
      </label>
      <div className="profile-actions">
        <small>{children}</small>
        {hasKey && (
          <button type="button" className="voice-btn" disabled={disabled} onClick={onDelete}>
            Borrar
          </button>
        )}
        <button type="button" className="voice-btn" disabled={disabled || !key.trim()} onClick={save}>
          Guardar
        </button>
      </div>
    </div>
  );
}
