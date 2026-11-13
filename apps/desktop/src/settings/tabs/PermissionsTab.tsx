import { Group, Row, Value } from "../controls";
import "./PermissionsTab.css";

const PERMISSION_LEVELS = [
  { level: "Normal", tone: "ok", text: "Abrir apps, buscar archivos, volumen, recordatorios. No exige nada." },
  { level: "Delicado", tone: "warn", text: "Comandos de terminal, borrar archivos, enviar mensajes. Pide confirmación por voz o clic." },
  { level: "Crítico", tone: "danger", text: "Protecciones del sistema, registro, instalar programas, usuarios. Exige la clave secreta." },
  { level: "Prohibido", tone: "off", text: "Formatear discos, borrados masivos, leer credenciales. No se ejecuta nunca." },
];

export function PermissionsTab() {
  return (
    <>
      <Group title="Niveles de permiso">
        <ul className="levels">
          {PERMISSION_LEVELS.map((p) => (
            <li key={p.level}>
              <span className="dot" data-tone={p.tone} />
              <strong>{p.level}</strong>
              <span className="muted">{p.text}</span>
            </li>
          ))}
        </ul>
      </Group>

      <Group title="Clave secreta">
        <Row
          label="Clave del nivel crítico"
          text="La verifica la app, nunca el modelo. También sirve para bajar una acción del nivel crítico."
        >
          <Value>Sin configurar</Value>
        </Row>
      </Group>
    </>
  );
}
