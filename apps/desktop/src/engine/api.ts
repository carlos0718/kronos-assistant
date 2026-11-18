// Pedidos HTTP al motor: los usa la pantalla de configuración.

/** Dónde escucha el motor y con qué token se entra. Lo entrega `useEngine`. */
export type Connection = { port: number; token: string };

export type Voice = {
  id: string;
  name: string;
  language: "es" | "en";
  /** Vacío si no se sabe. */
  region: string;
  /** null si no se sabe. */
  gender: "female" | "male" | null;
  /** Piper corre en la computadora; ElevenLabs, en la nube y de pago. */
  provider: "piper" | "elevenlabs";
};

export type VoiceList = { current: string; voices: Voice[] };

async function request(connection: Connection, path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`http://127.0.0.1:${connection.port}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${connection.token}`, "Content-Type": "application/json", ...init.headers },
  });
  if (!response.ok) {
    // El motor manda el motivo en `detail`, ya redactado para mostrarlo.
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `El motor respondió ${response.status}.`);
  }
  return response;
}

export async function listVoices(connection: Connection): Promise<VoiceList> {
  return (await request(connection, "/voices")).json();
}

export async function selectVoice(connection: Connection, id: string): Promise<void> {
  await request(connection, "/voices/current", { method: "PUT", body: JSON.stringify({ id }) });
}

/** Hace sonar una frase de muestra. Vuelve cuando terminó de sonar. */
export async function previewVoice(connection: Connection, id: string): Promise<void> {
  await request(connection, `/voices/${encodeURIComponent(id)}/preview`, { method: "POST" });
}

/** Si Kronos escucha su nombre para activarse. */
export async function getWakeWord(connection: Connection): Promise<boolean> {
  const body: { enabled: boolean } = await (await request(connection, "/wake-word")).json();
  return body.enabled;
}

export async function setWakeWord(connection: Connection, enabled: boolean): Promise<void> {
  await request(connection, "/wake-word", { method: "PUT", body: JSON.stringify({ enabled }) });
}

/** Cómo se llama el usuario y qué cuenta de sí mismo. */
export type Profile = { name: string; about: string };

export async function getProfile(connection: Connection): Promise<Profile> {
  return (await request(connection, "/profile")).json();
}

export async function setProfile(connection: Connection, profile: Profile): Promise<void> {
  await request(connection, "/profile", { method: "PUT", body: JSON.stringify(profile) });
}

/** Segundos que Kronos sigue escuchando después de responder; con cero no sigue. */
export async function getFollowUp(connection: Connection): Promise<number> {
  const body: { seconds: number } = await (await request(connection, "/follow-up")).json();
  return body.seconds;
}

export async function setFollowUp(connection: Connection, seconds: number): Promise<void> {
  await request(connection, "/follow-up", { method: "PUT", body: JSON.stringify({ seconds }) });
}

/** Milisegundos de silencio que dan por terminada la frase del usuario. */
export async function getEndPause(connection: Connection): Promise<number> {
  const body: { milliseconds: number } = await (await request(connection, "/end-pause")).json();
  return body.milliseconds;
}

export async function setEndPause(connection: Connection, milliseconds: number): Promise<void> {
  await request(connection, "/end-pause", { method: "PUT", body: JSON.stringify({ milliseconds }) });
}

/** Las carpetas que todo usuario tiene, como las nombra el motor (`core/platform.py`). */
export type KnownFolder = "desktop" | "documents" | "downloads" | "pictures" | "music" | "videos" | "home";

/** Dónde puede mirar Kronos: fuera de estas carpetas no busca ni abre nada. */
export type FolderAccess = {
  known: KnownFolder[];
  /** Otras carpetas que sumó el usuario, con su ruta completa. */
  extra: string[];
  /** Cuántos niveles adentro busca lo que no está justo ahí. */
  depth: number;
};

export async function getFolderAccess(connection: Connection): Promise<FolderAccess> {
  return (await request(connection, "/folder-access")).json();
}

/** Falla con el motivo, para mostrarlo, si una carpeta no existe. */
export async function setFolderAccess(connection: Connection, access: FolderAccess): Promise<void> {
  await request(connection, "/folder-access", { method: "PUT", body: JSON.stringify(access) });
}
