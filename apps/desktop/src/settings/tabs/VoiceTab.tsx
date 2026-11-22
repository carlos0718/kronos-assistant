import { useEffect, useRef, useState } from "react";
import {
  type Connection,
  getEndPause,
  getFollowUp,
  listVoices,
  previewVoice,
  selectVoice,
  setEndPause,
  setFollowUp,
  setVoiceKey,
  type Voice,
  type VoiceList,
} from "../../engine/api";
import { Group, Row, Slider, Value } from "../controls";
import { KeyField } from "./KeyField";
import "./VoiceTab.css";

// Las voces de ElevenLabs van primero y aparte: hablan cualquier idioma y son de pago.
const GROUPS = [
  {
    key: "elevenlabs",
    title: "Voces de ElevenLabs",
    hint: "en la nube y de pago; se suman desde tu cuenta de ElevenLabs",
    matches: (voice: Voice) => voice.provider === "elevenlabs",
  },
  {
    key: "es",
    title: "Voces en español",
    hint: "la primera vez que probás una voz, se descarga",
    matches: (voice: Voice) => voice.provider === "piper" && voice.language === "es",
  },
  {
    key: "en",
    title: "Voces en inglés",
    hint: "la primera vez que probás una voz, se descarga",
    matches: (voice: Voice) => voice.provider === "piper" && voice.language === "en",
  },
];
const GENDER_LABEL = { female: "Mujer", male: "Hombre" };

function describe(voice: Voice): string {
  return [voice.gender && GENDER_LABEL[voice.gender], voice.region].filter(Boolean).join(" · ");
}
// El mismo tope que valida el motor (`core/follow_up.py`).
const FOLLOW_UP_MAX = 60;
// El mismo rango que valida el motor (`core/end_pause.py`), en segundos.
const END_PAUSE_MIN = 0.5;
const END_PAUSE_MAX = 5;
const END_PAUSE_STEP = 0.1;
const decimal = new Intl.NumberFormat("es", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
// Mientras se arrastra el deslizador no se guarda cada paso: se espera a que se detenga.
const SAVE_DELAY_MS = 300;

export function VoiceTab({ connection }: { connection: Connection | null }) {
  // Las voces, la que está en uso y si hay clave de ElevenLabs: llegan juntas del motor.
  const [list, setList] = useState<VoiceList>({ current: "", has_key: false, voices: [] });
  const { voices, current, has_key: hasKey } = list;
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Hasta que el motor informa la espera guardada, el deslizador queda apagado.
  const [followUp, setFollowUpSeconds] = useState<number | null>(null);
  // En segundos, como se muestra; el motor la guarda en milisegundos.
  const [endPause, setEndPauseSeconds] = useState<number | null>(null);
  const saving = useRef<number | undefined>(undefined);
  const savingPause = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!connection) return;
    let stale = false;
    Promise.all([listVoices(connection), getFollowUp(connection), getEndPause(connection)])
      .then(([voiceList, seconds, milliseconds]) => {
        if (stale) return;
        setList(voiceList);
        setFollowUpSeconds(seconds);
        setEndPauseSeconds(milliseconds / 1000);
      })
      .catch((e) => !stale && setError(String(e.message ?? e)));
    return () => {
      stale = true;
    };
  }, [connection]);

  /** Guarda o borra la clave y vuelve a pedir las voces: aparecen o se van las de ElevenLabs. */
  async function saveKey(key: string): Promise<boolean> {
    if (!connection) return false;
    setError(null);
    try {
      await setVoiceKey(connection, key);
      setList(await listVoices(connection));
      return true;
    } catch (e) {
      setError(String((e as Error).message ?? e));
      return false;
    }
  }

  function changeFollowUp(seconds: number) {
    if (!connection) return;
    setFollowUpSeconds(seconds);
    setError(null);
    window.clearTimeout(saving.current);
    // No se cancela al salir de la pestaña: el último valor elegido se guarda igual.
    saving.current = window.setTimeout(() => {
      setFollowUp(connection, seconds).catch((e) => setError(String(e.message ?? e)));
    }, SAVE_DELAY_MS);
  }

  function changeEndPause(seconds: number) {
    if (!connection) return;
    setEndPauseSeconds(seconds);
    setError(null);
    window.clearTimeout(savingPause.current);
    savingPause.current = window.setTimeout(() => {
      // El deslizador da decimales inexactos (1,7000000000000002): se redondea al guardar.
      const milliseconds = Math.round(seconds * 10) * 100;
      setEndPause(connection, milliseconds).catch((e) => setError(String(e.message ?? e)));
    }, SAVE_DELAY_MS);
  }

  async function choose(id: string) {
    if (!connection) return;
    setError(null);
    try {
      await selectVoice(connection, id);
      setList((before) => ({ ...before, current: id }));
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  async function preview(id: string) {
    if (!connection) return;
    setError(null);
    setPreviewing(id);
    try {
      await previewVoice(connection, id);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setPreviewing(null);
    }
  }

  return (
    <>
      {error && <p className="panel-error">{error}</p>}

      {!connection && (
        <Group title="Voz de Kronos">
          <Row label="Voz" text="Las voces se cargan cuando el motor está conectado.">
            <Value>Sin conexión</Value>
          </Row>
        </Group>
      )}

      {connection && (
        <Group title="ElevenLabs" hint="voces más humanas, en la nube y de pago">
          <KeyField
            label="Clave de ElevenLabs"
            placeholder="sk_…"
            hasKey={hasKey}
            disabled={!connection}
            onSave={saveKey}
            onDelete={() => saveKey("")}
          >
            {hasKey
              ? "Guardada en el Administrador de credenciales de Windows, no en un archivo. Lo que dice Kronos se genera en ElevenLabs, que lo cobra en tu cuenta."
              : "Con tu clave se suman las voces de tu cuenta. Al crearla, dale permiso de Text to Speech y de Voices (leer)."}
          </KeyField>
        </Group>
      )}

      {GROUPS.map(({ key, title, hint, matches }) => {
        const inGroup = voices.filter(matches);
        if (!inGroup.length) return null;
        return (
          <Group key={key} title={title} hint={hint}>
            {inGroup.map((voice) => (
              <Row key={voice.id} label={voice.name} text={describe(voice)}>
                <span className="voice-actions">
                  <button
                    type="button"
                    className="voice-btn"
                    onClick={() => preview(voice.id)}
                    disabled={previewing !== null}
                  >
                    {previewing === voice.id ? "Sonando…" : "Probar"}
                  </button>
                  <button
                    type="button"
                    className="voice-btn"
                    aria-pressed={voice.id === current}
                    onClick={() => choose(voice.id)}
                  >
                    {voice.id === current ? "En uso" : "Usar"}
                  </button>
                </span>
              </Row>
            ))}
          </Group>
        );
      })}

      <Group title="Conversación" hint="con 0, la conversación termina después de cada respuesta">
        <Slider
          label="Seguir escuchando después de responder (segundos)"
          icon="mic"
          value={followUp ?? 0}
          onChange={changeFollowUp}
          max={FOLLOW_UP_MAX}
          disabled={!connection || followUp === null}
        />
      </Group>

      <Group title="Pausas al hablar" hint="más larga no te corta en una pausa, pero Kronos tarda más en contestar">
        <Slider
          label="Silencio que da por terminada tu frase (segundos)"
          icon="mic"
          value={endPause ?? END_PAUSE_MIN}
          onChange={changeEndPause}
          min={END_PAUSE_MIN}
          max={END_PAUSE_MAX}
          step={END_PAUSE_STEP}
          format={(seconds) => decimal.format(seconds)}
          disabled={!connection || endPause === null}
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
