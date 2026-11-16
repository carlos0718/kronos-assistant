import type { Confirmation } from "../engine/useEngine";
import "./Confirm.css";

type Props = {
  confirmation: Confirmation;
  onAnswer: (approved: boolean) => void;
};

/** La pregunta de Kronos antes de una acción delicada: se contesta con un clic o por voz. */
export function Confirm({ confirmation, onAnswer }: Props) {
  return (
    <fieldset className="confirm">
      <legend className="confirm-question">¿Confirmás {confirmation.summary}?</legend>
      {confirmation.detail && <code className="confirm-detail">{confirmation.detail}</code>}
      <div className="confirm-actions">
        <button type="button" className="confirm-no" onClick={() => onAnswer(false)}>
          No
        </button>
        <button type="button" className="confirm-yes" onClick={() => onAnswer(true)}>
          Sí
        </button>
      </div>
      <p className="confirm-hint">También podés decir «sí, confirmo» o «no».</p>
    </fieldset>
  );
}
