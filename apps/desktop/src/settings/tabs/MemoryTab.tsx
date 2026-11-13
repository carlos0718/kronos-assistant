import { useState } from "react";
import { Group, Row, Toggle, Value } from "../controls";

export function MemoryTab() {
  // Valores de muestra: todavía no se guardan ni llegan al motor.
  const [shareMemory, setShareMemory] = useState(true);
  const [sensitive, setSensitive] = useState(false);

  return (
    <>
      <Group title="Lo que Kronos recuerda">
        <Row label="Perfil y datos" text="Preferencias y cosas que le pediste recordar.">
          <Value>Vacío</Value>
        </Row>
        <Row label="Historial" text="Tus conversaciones, con un resumen de cada una.">
          <Value>Vacío</Value>
        </Row>
      </Group>

      <Group title="Privacidad">
        <Row
          label="Compartir la memoria con modelos en la nube"
          text="Si el modelo está en la nube, los recuerdos relevantes viajan al proveedor."
        >
          <Toggle checked={shareMemory} onChange={setShareMemory} />
        </Row>
        <Row label="Modo sensible" text="Al dictar datos privados no se guarda audio ni transcripción.">
          <Toggle checked={sensitive} onChange={setSensitive} />
        </Row>
      </Group>
    </>
  );
}
