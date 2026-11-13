import type { CSSProperties, ReactNode } from "react";
import { Icon } from "./icons";
import "./controls.css";

export function Group({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div className="group">
      <h2>
        {title}
        {hint && <span className="group-hint">{hint}</span>}
      </h2>
      {children}
    </div>
  );
}

/** Una opción: nombre y explicación a la izquierda, control a la derecha. */
export function Row({ label, text, children }: { label: string; text?: string; children: ReactNode }) {
  return (
    <div className="row">
      <div className="row-text">
        <span>{label}</span>
        {text && <small>{text}</small>}
      </div>
      {children}
    </div>
  );
}

/** Valor que todavía no se puede editar desde acá. */
export function Value({ children }: { children: ReactNode }) {
  return <span className="value">{children}</span>;
}

export function Toggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className="toggle"
      onClick={() => onChange(!checked)}
    />
  );
}

type SegmentedProps = { options: string[]; value: string; onChange: (value: string) => void };

export function Segmented({ options, value, onChange }: SegmentedProps) {
  return (
    <div className="segmented" role="radiogroup">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={option === value}
          onClick={() => onChange(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

type SliderProps = {
  label: string;
  icon: Parameters<typeof Icon>[0]["name"];
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
};

export function Slider({ label, icon, value, onChange, min = 0, max = 100 }: SliderProps) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="slider">
      <div className="slider-head">{label}</div>
      <div className="slider-row">
        <span className="slider-icon">
          <Icon name={icon} />
        </span>
        <div className="slider-body">
          <input
            type="range"
            min={min}
            max={max}
            value={value}
            aria-label={label}
            style={{ "--pct": `${pct}%` } as CSSProperties}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          <div className="slider-range">
            <span>{min}</span>
            <span>{max}</span>
          </div>
        </div>
        <output className="slider-value">{value}</output>
      </div>
    </div>
  );
}
