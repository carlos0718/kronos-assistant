// Pedidos HTTP al motor: los usa la pantalla de configuración.

/** Dónde escucha el motor y con qué token se entra. Lo entrega `useEngine`. */
export type Connection = { port: number; token: string };

export type Voice = {
  id: string;
  name: string;
  language: "es" | "en";
  region: string;
  gender: "female" | "male";
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
