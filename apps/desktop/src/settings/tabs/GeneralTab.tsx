import { useState } from "react";
import { type AssistantState, STATE_LABEL } from "../../engine/useEngine";
import { Group, Row, Segmented, Toggle } from "../controls";
import { Icon } from "../icons";
import "./GeneralTab.css";

type Props = { state: AssistantState; connected: boolean; busy: boolean; onSummon: () => void };

export function GeneralTab({ state, connected, busy, onSummon }: Props) {
  // Valores de muestra: todavía no se guardan ni llegan al motor.
  const [language, setLanguage] = useState("Español");
  const [wakeWord, setWakeWord] = useState(false);
  const [autoActivate, setAutoActivate] = useState(false);

  return (
    <>
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
            <kbd>Alt</kbd>
            <kbd>K</kbd>
          </span>
        </Row>
        <Row label='Palabra de activación "Kronos"' text="Kronos escucha su nombre para activarse.">
          <Toggle checked={wakeWord} onChange={setWakeWord} />
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
