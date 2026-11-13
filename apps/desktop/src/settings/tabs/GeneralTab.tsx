import { useEffect, useState } from "react";
import { type Connection, getWakeWord, setWakeWord } from "../../engine/api";
import { type AssistantState, STATE_LABEL } from "../../engine/useEngine";
import { Group, Row, Segmented, Toggle } from "../controls";
import { Icon } from "../icons";
import "./GeneralTab.css";

type Props = {
  state: AssistantState;
  connection: Connection | null;
  busy: boolean;
  onSummon: () => void;
};

export function GeneralTab({ state, connection, busy, onSummon }: Props) {
  const connected = state !== "disconnected";
  const [wakeWord, setWakeWordShown] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Valores de muestra: todavía no se guardan ni llegan al motor.
  const [language, setLanguage] = useState("Español");
  const [autoActivate, setAutoActivate] = useState(false);

  useEffect(() => {
    if (!connection) return;
    let stale = false;
    getWakeWord(connection)
      .then((enabled) => !stale && setWakeWordShown(enabled))
      .catch((e) => !stale && setError(String(e.message ?? e)));
    return () => {
      stale = true;
    };
  }, [connection]);

  async function toggleWakeWord(enabled: boolean) {
    if (!connection) return;
    setError(null);
    try {
      await setWakeWord(connection, enabled);
      setWakeWordShown(enabled);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  return (
    <>
      {error && <p className="panel-error">{error}</p>}

      <Group title="Probar a Kronos" hint="hacé clic en el botón para hablarle">
        <div className="tester">
          <button
            type="button"
            className="round-btn"
            data-busy={busy}
            aria-label={busy ? "Cortar" : "Probar ahora"}
            onClick={onSummon}
            disabled={!connected}
          >
            <Icon name={busy ? "stop" : "mic"} />
          </button>
          <div className="dots" data-busy={busy} />
          <span className="tester-state">{STATE_LABEL[state]}</span>
        </div>
      </Group>

      <Group title="Idioma">
        <Row label="Idioma de la voz y de la interfaz">
          <Segmented options={["Español", "English"]} value={language} onChange={setLanguage} />
        </Row>
      </Group>

      <Group title="Activación">
        <Row label="Atajo de teclado" text="Invoca a Kronos y también lo corta mientras habla.">
          <span className="keys">
            <kbd>Ctrl</kbd>
            <kbd>Shift</kbd>
            <kbd>K</kbd>
          </span>
        </Row>
        <Row
          label='Palabra de activación "Kronos"'
          text="Decí «Kronos» y tu pedido. El micrófono queda abierto, pero nada de lo que oye sale de tu equipo ni se guarda."
        >
          <Toggle checked={wakeWord} onChange={toggleWakeWord} disabled={!connection} />
        </Row>
        <Row
          label="Activación automática"
          text="Para rutinas y notificaciones: avisa con un sonido y espera tu permiso antes de hablar."
        >
          <Toggle checked={autoActivate} onChange={setAutoActivate} />
        </Row>
      </Group>
    </>
  );
}
