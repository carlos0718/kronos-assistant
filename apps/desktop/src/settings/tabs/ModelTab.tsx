import { useState } from "react";
import { Group, Row, Segmented, Toggle, Value } from "../controls";

const MODEL_BY_TASK = [
  "Notificaciones y eventos del sistema",
  "Rutinas y recordatorios simples",
  "Conversación, planificación y comandos",
];

export function ModelTab() {
  // Valores de muestra: todavía no se guardan ni llegan al motor.
  const [connection, setConnection] = useState("API key");
  const [fallback, setFallback] = useState(false);

  return (
    <>
      <Group title="Conexión">
        <Row label="Cómo se conecta Kronos">
          <Segmented
            options={["Local", "API key", "Inicio de sesión"]}
            value={connection}
            onChange={setConnection}
          />
        </Row>
        <Row label="Proveedor">
          <Value>Sin configurar</Value>
        </Row>
        <Row label="Modelo principal" text="El que se usa por defecto.">
          <Value>Sin configurar</Value>
        </Row>
      </Group>

      <Group title="Modo híbrido">
        <Row label="Modelo de respaldo" text="Un modelo local liviano que entra cuando no hay internet o falla la nube.">
          <Toggle checked={fallback} onChange={setFallback} />
        </Row>
      </Group>

      <Group title="Modelo por función">
        {MODEL_BY_TASK.map((task) => (
          <Row key={task} label={task}>
            <Value>Principal</Value>
          </Row>
        ))}
      </Group>
    </>
  );
}
