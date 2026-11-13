import { useEffect, useState } from "react";
import { type Connection, getProfile, type Profile, setProfile } from "../../engine/api";
import { Group } from "../controls";
import "./ProfileGroup.css";

// Los mismos topes que valida el motor (`api/profile.py`).
const NAME_MAX = 60;
const ABOUT_MAX = 500;

/** Cómo se llama el usuario y qué cuenta de sí mismo: Kronos lo usa como contexto. */
export function ProfileGroup({ connection }: { connection: Connection | null }) {
  const [saved, setSaved] = useState<Profile>({ name: "", about: "" });
  const [draft, setDraft] = useState<Profile>({ name: "", about: "" });
  const [error, setError] = useState<string | null>(null);
  const [justSaved, setJustSaved] = useState(false);

  useEffect(() => {
    if (!connection) return;
    let stale = false;
    getProfile(connection)
      .then((profile) => {
        if (stale) return;
        setSaved(profile);
        setDraft(profile);
      })
      .catch((e) => !stale && setError(String(e.message ?? e)));
    return () => {
      stale = true;
    };
  }, [connection]);

  const changed = draft.name !== saved.name || draft.about !== saved.about;

  function edit(change: Partial<Profile>) {
    setJustSaved(false);
    setDraft((current) => ({ ...current, ...change }));
  }

  async function save() {
    if (!connection) return;
    setError(null);
    try {
      await setProfile(connection, draft);
      // El motor guarda el texto sin espacios en los bordes: se muestra igual.
      const clean = { name: draft.name.trim(), about: draft.about.trim() };
      setSaved(clean);
      setDraft(clean);
      setJustSaved(true);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    }
  }

  return (
    <Group title="Sobre vos" hint="para que Kronos te llame por tu nombre">
      {error && <p className="panel-error">{error}</p>}
      <div className="profile">
        <label>
          <span>Tu nombre</span>
          <input
            type="text"
            value={draft.name}
            maxLength={NAME_MAX}
            placeholder="Cómo querés que te llame"
            disabled={!connection}
            onChange={(event) => edit({ name: event.target.value })}
          />
        </label>
        <label>
          <span>Una descripción corta</span>
          <textarea
            value={draft.about}
            maxLength={ABOUT_MAX}
            rows={3}
            placeholder="A qué te dedicás, qué te gusta, cómo preferís que te hable…"
            disabled={!connection}
            onChange={(event) => edit({ about: event.target.value })}
          />
        </label>
        <div className="profile-actions">
          <small>
            Se queda en tu equipo. Se le pasa al modelo en cada conversación: si usás un modelo en la nube, viaja con
            ella.
          </small>
          <span className="profile-count">
            {draft.about.length}/{ABOUT_MAX}
          </span>
          <button type="button" className="voice-btn" disabled={!connection || !changed} onClick={save}>
            {justSaved ? "Guardado" : "Guardar"}
          </button>
        </div>
      </div>
    </Group>
  );
}
