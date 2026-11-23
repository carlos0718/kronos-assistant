import { useCallback, useEffect, useState } from "react";
import { type ActionLevel, type Connection, getToolLevels, setToolLevel } from "../../engine/api";
import { Group, Row, Segmented, Value } from "../controls";
import "./ProfileGroup.css";

// En el orden de los niveles del motor (`core/tools.py`).
const LEVEL_NAMES = ["Normal", "Delicado", "Crítico"];
const CRITICAL = 3;

function levelName(level: number): string {
  return LEVEL_NAMES[level - 1] ?? "Prohibido";
}

/** El nivel de permiso de cada acción: subirlo siempre se puede; bajar uno crítico pide la clave secreta. */
export function ToolLevelsGroup({ connection }: { connection: Connection | null }) {
  const [actions, setActions] = useState<ActionLevel[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Bajar algo del nivel crítico espera acá hasta que se escriba la clave.
  const [pending, setPending] = useState<{ name: string; level: number } | null>(null);
  const [secret, setSecret] = useState("");

  const reload = useCallback(async () => {
    if (!connection) return;
    setActions(await getToolLevels(connection));
  }, [connection]);

  useEffect(() => {
    reload().catch((e) => setError(String(e.message ?? e)));
  }, [reload]);

  async function apply(name: string, level: number, key?: string) {
    if (!connection) return;
    setError(null);
    try {
      await setToolLevel(connection, name, level, key);
      setPending(null);
      setSecret("");
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
    // También si falló: muestra lo que quedó, y el motor pudo contar un intento fallido.
    await reload().catch(() => {});
  }

  function choose(action: ActionLevel, level: number) {
    if (level === action.level) return;
    setError(null);
    if (action.level >= CRITICAL && level < CRITICAL) {
      setPending({ name: action.name, level });
      return;
    }
    setPending(null);
    apply(action.name, level);
  }

  return (
    <Group title="Nivel de cada acción" hint="subirlo siempre se puede; bajar uno crítico pide la clave secreta">
      {error && <p className="panel-error">{error}</p>}
      {!connection && (
        <Row label="Acciones" text="Se cargan cuando el motor está conectado.">
          <Value>Sin conexión</Value>
        </Row>
      )}
      {actions?.map((action) => (
        <div key={action.name}>
          <Row
            label={action.label}
            text={
              action.level === action.factory ? undefined : `De fábrica: ${levelName(action.factory).toLowerCase()}`
            }
          >
            {action.fixed ? (
              <Value>Prohibido</Value>
            ) : (
              <Segmented
                options={LEVEL_NAMES.slice(action.lowest - 1)}
                value={levelName(action.level)}
                onChange={(name) => choose(action, LEVEL_NAMES.indexOf(name) + 1)}
              />
            )}
          </Row>
          {pending?.name === action.name && (
            <div className="profile">
              <label>
                <span>
                  Clave secreta, para bajar «{action.label}» a {levelName(pending.level).toLowerCase()}
                </span>
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  value={secret}
                  onChange={(event) => setSecret(event.target.value)}
                />
              </label>
              <div className="profile-actions">
                <button type="button" className="voice-btn" onClick={() => setPending(null)}>
                  Cancelar
                </button>
                <button
                  type="button"
                  className="voice-btn"
                  disabled={!secret}
                  onClick={() => apply(pending.name, pending.level, secret)}
                >
                  Bajar el nivel
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </Group>
  );
}
