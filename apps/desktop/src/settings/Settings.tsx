import { useState, type CSSProperties, type ReactNode } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Orb } from "../overlay/Orb";
import { STATE_LABEL, useEngine } from "../useEngine";
import { Icon } from "./icons";
import "./Settings.css";

// Las pestañas y sus opciones salen de las decisiones del README.
const TABS = [
  { id: "general", label: "General" },
  { id: "modelo", label: "Modelo" },
  { id: "voz", label: "Voz" },
  { id: "permisos", label: "Permisos" },
  { id: "rutinas", label: "Rutinas" },
  { id: "memoria", label: "Memoria" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const PERMISSION_LEVELS = [
  { level: "Normal", tone: "ok", text: "Abrir apps, buscar archivos, volumen, recordatorios. No exige nada." },
  { level: "Delicado", tone: "warn", text: "Comandos de terminal, borrar archivos, enviar mensajes. Pide confirmación por voz o clic." },
  { level: "Crítico", tone: "danger", text: "Protecciones del sistema, registro, instalar programas, usuarios. Exige la clave secreta." },
  { level: "Prohibido", tone: "off", text: "Formatear discos, borrados masivos, leer credenciales. No se ejecuta nunca." },
];

const MODEL_BY_TASK = ["Notificaciones y eventos del sistema", "Rutinas y recordatorios simples", "Conversación, planificación y comandos"];
const CALENDARS = ["Google Calendar", "Archivo o enlace .ics / CalDAV", "Outlook / Microsoft 365", "Notion"];

/** Ventana de configuración: escenario con la bolita a la izquierda y panel con pestañas a la derecha. */
export function Settings() {
  const { state, error } = useEngine();
  const [tab, setTab] = useState<TabId>("general");
  const connected = state !== "disconnected";
  const busy = connected && state !== "idle";
  const appWindow = getCurrentWindow();

  // Valores de muestra: todavía no se guardan ni llegan al motor.
  const [language, setLanguage] = useState("Español");
  const [wakeWord, setWakeWord] = useState(false);
  const [autoActivate, setAutoActivate] = useState(false);
  const [connection, setConnection] = useState("API key");
  const [fallback, setFallback] = useState(false);
  const [listenAfter, setListenAfter] = useState(5);
  const [shareMemory, setShareMemory] = useState(true);
  const [sensitive, setSensitive] = useState(false);

  const summon = () => invoke("summon_overlay");

  return (
    <div className="app">
      <header className="titlebar" data-tauri-drag-region>
        <div className="brand">
          <Orb state="idle" size={26} />
          <span className="brand-name">Kronos</span>
          <span className="brand-tagline">Tu asistente de voz</span>
        </div>
        <div className="titlebar-actions">
          <button type="button" className="win-btn" aria-label="Minimizar" onClick={() => appWindow.minimize()}>
            <Icon name="minimize" />
          </button>
          {/* Cerrar solo oculta la ventana: Kronos sigue en la bandeja. */}
          <button type="button" className="win-btn" aria-label="Cerrar" onClick={() => appWindow.close()}>
            <Icon name="close" />
          </button>
        </div>
      </header>

      <div className="layout">
        <section className="stage">
          <div className="stage-top">
            <button type="button" className="icon-btn" aria-label="Ir a General" onClick={() => setTab("general")}>
              <Icon name="home" />
            </button>
            <div className="chip">
              <span className="chip-label">Motor:</span>
              <span className="dot" data-on={connected} />
              <strong>{connected ? "Conectado" : "Sin conectar"}</strong>
            </div>
          </div>

          <div className="stage-orb">
            <Orb state={state} size={280} />
            <div className="stage-floor" />
            <p className="stage-state">{STATE_LABEL[state]}</p>
          </div>

          <div className="meter" data-state={state} aria-hidden="true">
            <div className="meter-track">
              <div className="meter-fill" />
            </div>
          </div>
          <button
            type="button"
            className="mic-btn"
            aria-label={busy ? "Cortar a Kronos" : "Hablar con Kronos"}
            onClick={summon}
            disabled={!connected}
          >
            <Icon name="mic" />
          </button>
        </section>

        <section className="panel">
          <div className="tabs" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                className="tab"
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {error && <p className="panel-error">{error}</p>}

          {tab === "general" && (
            <>
              <Group title="Probar a Kronos" hint="hacé clic en el botón para hablarle">
                <div className="tester">
                  <button
                    type="button"
                    className="round-btn"
                    data-busy={busy}
                    aria-label={busy ? "Cortar" : "Probar ahora"}
                    onClick={summon}
                    disabled={!connected}
                  >
                    <Icon name={busy ? "stop" : "mic"} />
                  </button>
                  <div className="dots" data-busy={busy} />
                  <span className="tester-state">{STATE_LABEL[state]}</span>
                </div>
              </Group>

              <Group title="Idioma">
                <Row label="Idioma de la voz y de la interfaz">
                  <Segmented options={["Español", "English"]} value={language} onChange={setLanguage} />
                </Row>
              </Group>

              <Group title="Activación">
                <Row label="Atajo de teclado" text="Invoca a Kronos y también lo corta mientras habla.">
                  <span className="keys">
                    <kbd>Ctrl</kbd>
                    <kbd>Alt</kbd>
                    <kbd>K</kbd>
                  </span>
                </Row>
                <Row label='Palabra de activación "Kronos"' text="Kronos escucha su nombre para activarse.">
                  <Toggle checked={wakeWord} onChange={setWakeWord} />
                </Row>
                <Row
                  label="Activación automática"
                  text="Para rutinas y notificaciones: avisa con un sonido y espera tu permiso antes de hablar."
                >
                  <Toggle checked={autoActivate} onChange={setAutoActivate} />
                </Row>
              </Group>
            </>
          )}

          {tab === "modelo" && (
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
          )}

          {tab === "voz" && (
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
          )}

          {tab === "permisos" && (
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
          )}

          {tab === "rutinas" && (
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
          )}

          {tab === "memoria" && (
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
          )}

          <p className="panel-note">
            Vista previa del diseño: estas opciones todavía no se guardan ni cambian el comportamiento de Kronos.
          </p>
        </section>
      </div>
    </div>
  );
}

function Group({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
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
function Row({ label, text, children }: { label: string; text?: string; children: ReactNode }) {
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
function Value({ children }: { children: ReactNode }) {
  return <span className="value">{children}</span>;
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
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

function Segmented({ options, value, onChange }: SegmentedProps) {
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

function Slider({ label, icon, value, onChange, min = 0, max = 100 }: SliderProps) {
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
