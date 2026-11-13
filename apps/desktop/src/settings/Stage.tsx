import { type AssistantState, STATE_LABEL } from "../engine/useEngine";
import { Orb } from "../shared/Orb";
import { Icon } from "./icons";
import "./Stage.css";

type Props = {
  state: AssistantState;
  connected: boolean;
  busy: boolean;
  onHome: () => void;
  onSummon: () => void;
};

/** Escenario: la bolita en grande, el estado del motor y el botón para hablarle. */
export function Stage({ state, connected, busy, onHome, onSummon }: Props) {
  return (
    <section className="stage">
      <div className="stage-top">
        <button type="button" className="icon-btn" aria-label="Ir a General" onClick={onHome}>
          <Icon name="home" />
        </button>
        <div className="chip">
          <span className="chip-label">Motor:</span>
          <span className="dot" data-on={connected} />
          <strong>{connected ? "Conectado" : "Sin conectar"}</strong>
        </div>
      </div>

      <div className="stage-orb">
        <Orb state={state} size={280} />
        <div className="stage-floor" />
        <p className="stage-state">{STATE_LABEL[state]}</p>
      </div>

      <div className="meter" data-state={state} aria-hidden="true">
        <div className="meter-track">
          <div className="meter-fill" />
        </div>
      </div>
      <button
        type="button"
        className="mic-btn"
        aria-label={busy ? "Cortar a Kronos" : "Hablar con Kronos"}
        onClick={onSummon}
        disabled={!connected}
      >
        <Icon name="mic" />
      </button>
    </section>
  );
}
