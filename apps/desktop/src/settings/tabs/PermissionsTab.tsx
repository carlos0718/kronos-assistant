import { open } from "@tauri-apps/plugin-dialog";
import { useEffect, useRef, useState } from "react";
import {
  type Connection,
  type FolderAccess,
  getFolderAccess,
  type KnownFolder,
  setFolderAccess,
} from "../../engine/api";
import { Group, Row, Slider, Toggle, Value } from "../controls";
import "./PermissionsTab.css";

const PERMISSION_LEVELS = [
  { level: "Normal", tone: "ok", text: "Abrir apps, buscar archivos, volumen, recordatorios. No exige nada." },
  {
    level: "Delicado",
    tone: "warn",
    text: "Comandos de terminal, borrar archivos, enviar mensajes. Pide confirmación por voz o clic.",
  },
  {
    level: "Crítico",
    tone: "danger",
    text: "Protecciones del sistema, registro, instalar programas, usuarios. Exige la clave secreta.",
  },
  {
    level: "Prohibido",
    tone: "off",
    text: "Formatear discos, borrados masivos, leer credenciales. No se ejecuta nunca.",
  },
];

// En el orden del motor (`core/platform.py`).
const KNOWN_FOLDERS: { id: KnownFolder; label: string; text?: string }[] = [
  { id: "desktop", label: "Escritorio" },
  { id: "documents", label: "Documentos" },
  { id: "downloads", label: "Descargas" },
  { id: "pictures", label: "Imágenes" },
  { id: "music", label: "Música" },
  { id: "videos", label: "Videos" },
  {
    id: "home",
    label: "Carpeta personal",
    text: "Contiene a las demás: podés pedirle cualquier carpeta de tu perfil diciendo el camino, salvo las que apagues acá.",
  },
];
// El mismo rango que valida el motor (`core/folder_access.py`).
const DEPTH_MIN = 1;
const DEPTH_MAX = 5;
const SAVE_DELAY_MS = 300;

/** El último tramo de una ruta de Windows: «D:\proyectos» es «proyectos», y «D:\» queda igual. */
function folderName(path: string): string {
  return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
}

export function PermissionsTab({ connection }: { connection: Connection | null }) {
  // Hasta que el motor informa lo guardado, los controles quedan apagados.
  const [access, setAccess] = useState<FolderAccess | null>(null);
  const [error, setError] = useState<string | null>(null);
  const savingDepth = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!connection) return;
    let stale = false;
    getFolderAccess(connection)
      .then((saved) => !stale && setAccess(saved))
      .catch((e) => !stale && setError(String(e.message ?? e)));
    return () => {
      stale = true;
    };
  }, [connection]);

  /** Guarda y muestra lo que quedó guardado: el motor quita repetidos y ordena las rutas. */
  async function save(next: FolderAccess) {
    if (!connection || !access) return;
    const before = access;
    setAccess(next);
    setError(null);
    try {
      await setFolderAccess(connection, next);
      setAccess(await getFolderAccess(connection));
    } catch (e) {
      setAccess(before);
      setError(String((e as Error).message ?? e));
    }
  }

  function toggleKnown(id: KnownFolder, enabled: boolean) {
    if (!access) return;
    const known = enabled ? [...access.known, id] : access.known.filter((k) => k !== id);
    save({ ...access, known });
  }

  async function addFolder() {
    if (!access) return;
    setError(null);
    try {
      const picked = await open({ directory: true, multiple: false, title: "Elegí una carpeta para Kronos" });
      if (typeof picked === "string") await save({ ...access, extra: [...access.extra, picked] });
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  function removeFolder(path: string) {
    if (!access) return;
    save({ ...access, extra: access.extra.filter((p) => p !== path) });
  }

  function changeDepth(depth: number) {
    if (!connection || !access) return;
    const next = { ...access, depth };
    setAccess(next);
    setError(null);
    window.clearTimeout(savingDepth.current);
    // No se cancela al salir de la pestaña: el último valor elegido se guarda igual.
    savingDepth.current = window.setTimeout(() => {
      setFolderAccess(connection, next).catch((e) => setError(String(e.message ?? e)));
    }, SAVE_DELAY_MS);
  }

  return (
    <>
      {error && <p className="panel-error">{error}</p>}

      <Group title="Carpetas que Kronos puede mirar" hint="fuera de estas no busca ni abre nada">
        {!connection && (
          <Row label="Carpetas" text="Se cargan cuando el motor está conectado.">
            <Value>Sin conexión</Value>
          </Row>
        )}
        {connection &&
          KNOWN_FOLDERS.map((folder) => (
            <Row key={folder.id} label={folder.label} text={folder.text}>
              <Toggle
                checked={access?.known.includes(folder.id) ?? false}
                label={folder.label}
                onChange={(enabled) => toggleKnown(folder.id, enabled)}
                disabled={!access}
              />
            </Row>
          ))}
        {access?.extra.map((path) => (
          <Row key={path} label={folderName(path)} text={path}>
            <button type="button" className="folder-btn" onClick={() => removeFolder(path)}>
              Quitar
            </button>
          </Row>
        ))}
        {connection && (
          <div className="folder-add">
            <button type="button" className="folder-btn" onClick={addFolder} disabled={!access}>
              Agregar carpeta…
            </button>
          </div>
        )}
      </Group>

      <Group title="Búsqueda" hint="más niveles encuentra carpetas más escondidas, pero tarda más">
        <Slider
          label="Niveles que busca adentro de cada carpeta"
          icon="folder"
          value={access?.depth ?? DEPTH_MIN}
          onChange={changeDepth}
          min={DEPTH_MIN}
          max={DEPTH_MAX}
          disabled={!access}
        />
      </Group>

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
