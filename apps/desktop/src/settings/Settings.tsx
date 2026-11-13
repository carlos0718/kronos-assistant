import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useState } from "react";
import { useEngine } from "../engine/useEngine";
import { Orb } from "../shared/Orb";
import { Icon } from "./icons";
// Va antes que los componentes: sus reglas base de botones tienen que cargarse primero.
import "./Settings.css";
import { Stage } from "./Stage";
import { GeneralTab } from "./tabs/GeneralTab";
import { MemoryTab } from "./tabs/MemoryTab";
import { ModelTab } from "./tabs/ModelTab";
import { PermissionsTab } from "./tabs/PermissionsTab";
import { RoutinesTab } from "./tabs/RoutinesTab";
import { VoiceTab } from "./tabs/VoiceTab";

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

/** Ventana de configuración: escenario con la bolita a la izquierda y panel con pestañas a la derecha. */
export function Settings() {
  const { state, error } = useEngine();
  const [tab, setTab] = useState<TabId>("general");
  const connected = state !== "disconnected";
  const busy = connected && state !== "idle";
  const appWindow = getCurrentWindow();

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
        <Stage state={state} connected={connected} busy={busy} onHome={() => setTab("general")} onSummon={summon} />

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

          {tab === "general" && <GeneralTab state={state} connected={connected} busy={busy} onSummon={summon} />}
          {tab === "modelo" && <ModelTab />}
          {tab === "voz" && <VoiceTab />}
          {tab === "permisos" && <PermissionsTab />}
          {tab === "rutinas" && <RoutinesTab />}
          {tab === "memoria" && <MemoryTab />}

          <p className="panel-note">
            Vista previa del diseño: estas opciones todavía no se guardan ni cambian el comportamiento de Kronos.
          </p>
        </section>
      </div>
    </div>
  );
}
