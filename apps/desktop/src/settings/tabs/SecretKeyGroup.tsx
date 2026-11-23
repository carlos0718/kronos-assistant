import { useCallback, useEffect, useState } from "react";
import { type Connection, getSecretKey, removeSecretKey, type SecretKeyStatus, setSecretKey } from "../../engine/api";
import { Group, Row, Value } from "../controls";
import "./ProfileGroup.css";

// El mismo mínimo que valida el motor (`core/secret.py`).
const MIN_LENGTH = 8;

/** Poner, cambiar y borrar la clave secreta del nivel crítico. */
export function SecretKeyGroup({ connection }: { connection: Connection | null }) {
  const [status, setStatus] = useState<SecretKeyStatus | null>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!connection) return;
    setStatus(await getSecretKey(connection));
  }, [connection]);

  useEffect(() => {
    reload().catch((e) => setError(String(e.message ?? e)));
  }, [reload]);

  /** Corre el pedido, muestra el motivo si falla y vacía los campos si sale bien. */
  async function run(action: (c: Connection) => Promise<void>) {
    if (!connection) return;
    setError(null);
    try {
      await action(connection);
      setCurrent("");
      setNext("");
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
    // También si falló: un intento fallido puede haber bloqueado el nivel crítico.
    await reload().catch(() => {});
  }

  const isSet = Boolean(status?.is_set);
  const locked = (status?.locked_for ?? 0) > 0;
  const ready = Boolean(connection && status) && !locked;

  return (
    <Group title="Clave secreta" hint="la pide el nivel crítico y se escribe: no se dicta">
      <Row
        label="Clave del nivel crítico"
        text="La verifica la app, nunca el modelo. Se guarda cifrada con tu cuenta de Windows, nunca en texto plano."
      >
        <Value>{!status ? "Sin conexión" : isSet ? "Configurada" : "Sin configurar"}</Value>
      </Row>
      <div className="profile">
        {error && <p className="panel-error">{error}</p>}
        {locked && (
          <p className="panel-error">
            Demasiados intentos fallidos: el nivel crítico está bloqueado unos{" "}
            {Math.ceil((status?.locked_for ?? 0) / 60)} minutos.
          </p>
        )}
        {isSet && (
          <label>
            <span>Clave actual</span>
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={current}
              disabled={!ready}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </label>
        )}
        <label>
          <span>{isSet ? "Clave nueva" : "Elegí una clave"}</span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            placeholder={`Al menos ${MIN_LENGTH} caracteres`}
            value={next}
            disabled={!ready}
            onChange={(event) => setNext(event.target.value)}
          />
        </label>
        <div className="profile-actions">
          <small>Si la perdés, no se puede recuperar: se borra desde el Administrador de credenciales.</small>
          {isSet && (
            <button
              type="button"
              className="voice-btn"
              disabled={!ready || !current}
              onClick={() => run((c) => removeSecretKey(c, current))}
            >
              Borrar
            </button>
          )}
          <button
            type="button"
            className="voice-btn"
            disabled={!ready || next.length < MIN_LENGTH || (isSet && !current)}
            onClick={() => run((c) => setSecretKey(c, next, isSet ? current : undefined))}
          >
            {isSet ? "Cambiar" : "Guardar"}
          </button>
        </div>
      </div>
    </Group>
  );
}
