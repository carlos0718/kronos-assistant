import { useEffect, useState } from "react";
import { type Connection, listVoices, previewVoice, selectVoice, type Voice } from "../../engine/api";
import { Group, Row, Slider, Value } from "../controls";
import "./VoiceTab.css";

const LANGUAGES = [
  { id: "es", title: "Voces en español" },
  { id: "en", title: "Voces en inglés" },
] as const;
const GENDER_LABEL = { female: "Mujer", male: "Hombre" };

export function VoiceTab({ connection }: { connection: Connection | null }) {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [current, setCurrent] = useState("");
  const [previewing, setPreviewing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Valor de muestra: todavía no se guarda ni llega al motor.
  const [listenAfter, setListenAfter] = useState(5);

  useEffect(() => {
    if (!connection) return;
    let stale = false;
    listVoices(connection)
      .then((list) => {
        if (stale) return;
        setVoices(list.voices);
        setCurrent(list.current);
      })
      .catch((e) => !stale && setError(String(e.message ?? e)));
    return () => {
      stale = true;
    };
  }, [connection]);

  async function choose(id: string) {
    if (!connection) return;
    setError(null);
    try {
      await selectVoice(connection, id);
      setCurrent(id);
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

      {LANGUAGES.map(({ id, title }) => {
        const inLanguage = voices.filter((voice) => voice.language === id);
        if (!inLanguage.length) return null;
        return (
          <Group key={id} title={title} hint="la primera vez que probás una voz, se descarga">
            {inLanguage.map((voice) => (
              <Row key={voice.id} label={voice.name} text={`${GENDER_LABEL[voice.gender]} · ${voice.region}`}>
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
