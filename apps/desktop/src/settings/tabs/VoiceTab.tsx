import { useState } from "react";
import { Group, Row, Slider, Value } from "../controls";

export function VoiceTab() {
  // Valor de muestra: todavía no se guarda ni llega al motor.
  const [listenAfter, setListenAfter] = useState(5);

  return (
    <>
      <Group title="Voz de Kronos">
        <Row label="Voz" text="Kronos funciona con cualquier voz; la elegís vos.">
          <Value>Sin configurar</Value>
        </Row>
      </Group>

      <Group title="Conversación">
        <Slider
          label="Seguir escuchando después de responder (segundos)"
          icon="mic"
          value={listenAfter}
          onChange={setListenAfter}
          max={15}
        />
      </Group>

      <Group title="Vocabulario personal">
        <Row
          label="Palabras que Kronos debe reconocer"
          text="Nombres propios, apps y términos técnicos que se le pasan al reconocedor de voz."
        >
          <Value>0 palabras</Value>
        </Row>
      </Group>
    </>
  );
}
