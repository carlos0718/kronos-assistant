import { useEffect, useState } from "react";
import { type Connection, getModel, type ModelStatus, setModel, setModelKey } from "../../engine/api";
import { Group, Row, Segmented, Toggle, Value } from "../controls";
import "./ProfileGroup.css";
import "./ModelTab.css";

const LOCAL = "En tu computadora";
const CLAUDE = "Claude";

// Precios de Anthropic de noviembre de 2026, en dólares por millón de tokens (entrada / salida).
const CLAUDE_MODELS: Record<string, { label: string; text: string }> = {
  "claude-opus-5-5": { label: "Opus 5.5", text: "El más capaz. US$ 4 / 20 por millón de tokens." },
  "claude-sonnet-5-5": { label: "Sonnet 5.5", text: "Rápido y capaz. US$ 2 / 10 por millón de tokens." },
  "claude-haiku-5-5": { label: "Haiku 5.5", text: "El más rápido y barato. US$ 0,10 / 0,50 por millón." },
};

const MODEL_BY_TASK = [
  "Notificaciones y eventos del sistema",
  "Rutinas y recordatorios simples",
  "Conversación, planificación y comandos",
];

export function ModelTab({ connection }: { connection: Connection | null }) {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Valor de muestra: todavía no se guarda ni llega al motor.
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    if (!connection) return;
    let stale = false;
    getModel(connection)
      .then((current) => !stale && setStatus(current))
      .catch((e) => !stale && setError(String(e.message ?? e)));
    return () => {
      stale = true;
    };
  }, [connection]);

  async function run(change: () => Promise<void>) {
    if (!connection) return;
    setError(null);
    try {
      await change();
      setStatus(await getModel(connection));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  const claude = status?.provider === "anthropic";
  const models = status?.models ?? Object.keys(CLAUDE_MODELS);
  const chosen = status?.model || models[0];
  const labelOf = (id: string) => CLAUDE_MODELS[id]?.label ?? id;

  return (
    <>
      <Group title="Quién responde">
        {error && <p className="panel-error">{error}</p>}
        <Row label="Modelo" text={claude ? "En la nube, de pago." : "Gratis; lo que decís no sale de tu equipo."}>
          <Segmented
            options={[LOCAL, CLAUDE]}
            value={claude ? CLAUDE : LOCAL}
            onChange={(option) =>
              connection && run(() => setModel(connection, option === CLAUDE ? "anthropic" : "ollama", ""))
            }
          />
        </Row>
        {!claude && (
          <Row label="Modelo local">
            <Value>Ollama</Value>
          </Row>
        )}
        {claude && (
          <>
            <Row label="Modelo de Claude" text={CLAUDE_MODELS[chosen]?.text}>
              <Segmented
                options={models.map(labelOf)}
                value={labelOf(chosen)}
                onChange={(label) => {
                  const id = models.find((model) => labelOf(model) === label) ?? models[0];
                  if (connection) run(() => setModel(connection, "anthropic", id));
                }}
              />
            </Row>
            <div className="profile model-key">
              <label>
                <span>Clave de Anthropic</span>
                <input
                  type="password"
                  value={key}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder={status?.has_key ? "Ya hay una clave guardada" : "sk-ant-…"}
                  disabled={!connection}
                  onChange={(event) => setKey(event.target.value)}
                />
              </label>
              <div className="profile-actions">
                <small>
                  {status?.has_key
                    ? "Guardada en el Administrador de credenciales de Windows, no en un archivo."
                    : "Falta la clave: hasta que la cargues, Kronos no puede responder."}{" "}
                  Lo que decís viaja a Anthropic, que lo cobra en tu cuenta.
                </small>
                {status?.has_key && (
                  <button
                    type="button"
                    className="voice-btn"
                    disabled={!connection}
                    onClick={() => connection && run(() => setModelKey(connection, ""))}
                  >
                    Borrar
                  </button>
                )}
                <button
                  type="button"
                  className="voice-btn"
                  disabled={!connection || !key.trim()}
                  onClick={() =>
                    connection &&
                    run(async () => {
                      await setModelKey(connection, key);
                      setKey("");
                    })
                  }
                >
                  Guardar
                </button>
              </div>
            </div>
          </>
        )}
      </Group>

      <Group title="Modo híbrido">
        <Row
          label="Modelo de respaldo"
          text="Un modelo local liviano que entra cuando no hay internet o falla la nube."
        >
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
