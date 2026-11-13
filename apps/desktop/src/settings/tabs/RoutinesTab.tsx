import { Group, Row, Value } from "../controls";

const CALENDARS = ["Google Calendar", "Archivo o enlace .ics / CalDAV", "Outlook / Microsoft 365", "Notion"];

export function RoutinesTab() {
  return (
    <>
      <Group title="Rutinas">
        <Row label="Rutinas creadas" text="Se crean por voz, desde esta pantalla, desde el calendario o en un archivo de texto.">
          <Value>Ninguna</Value>
        </Row>
      </Group>

      <Group title="Calendarios">
        {CALENDARS.map((calendar) => (
          <Row key={calendar} label={calendar}>
            <Value>Sin conectar</Value>
          </Row>
        ))}
      </Group>

      <Group title="Notificaciones">
        <Row label="Apps permitidas" text="Kronos solo lee las notificaciones de las apps que elijas.">
          <Value>Ninguna</Value>
        </Row>
      </Group>
    </>
  );
}
