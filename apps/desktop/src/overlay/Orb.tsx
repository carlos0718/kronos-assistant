import { useId } from "react";
import type { AssistantState } from "../useEngine";
import "./Orb.css";

type Props = { state: AssistantState; size?: number };

// Anillo orbital: una elipse inclinada. `pathLength` permite animar el tramo
// brillante que la recorre sin depender de su perímetro real.
function Ring({ arc, clipPath }: { arc: string; clipPath?: string }) {
  const shape = { cx: 60, cy: 60, rx: 50, ry: 15, fill: "none", pathLength: 100 };
  return (
    <g clipPath={clipPath}>
      <ellipse {...shape} className="orb-ring-track" />
      <ellipse {...shape} className="orb-ring-arc" stroke={arc} />
    </g>
  );
}

/** La bolita de Kronos: una esfera con un anillo orbital, animada según el estado. */
export function Orb({ state, size = 96 }: Props) {
  const id = useId();
  const sphere = `${id}-sphere`;
  const arc = `${id}-arc`;
  const front = `${id}-front`;

  return (
    <svg className="orb" data-state={state} width={size} height={size} viewBox="0 0 120 120" aria-hidden="true">
      <defs>
        <radialGradient id={sphere} cx="38%" cy="32%" r="75%">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="45%" stopColor="var(--violet)" />
          <stop offset="100%" stopColor="var(--indigo)" />
        </radialGradient>
        <linearGradient id={arc} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="var(--accent)" />
          <stop offset="100%" stopColor="var(--violet)" />
        </linearGradient>
        {/* Mitad delantera del anillo: la que pasa por delante de la esfera. */}
        <clipPath id={front}>
          <rect x="0" y="60" width="120" height="60" />
        </clipPath>
      </defs>

      <g transform="rotate(-20 60 60)">
        <Ring arc={`url(#${arc})`} />
        <circle className="orb-sphere" cx="60" cy="60" r="30" fill={`url(#${sphere})`} />
        <Ring arc={`url(#${arc})`} clipPath={`url(#${front})`} />
      </g>
    </svg>
  );
}
