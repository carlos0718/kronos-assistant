// Vocabulario del protocolo motor ↔ interfaz: estados y tipos de mensaje.
//
// El motor tiene su copia en `engine/src/kronos_engine/core/protocol.py`.
// Cambiar una obliga a cambiar la otra: lo verifica `engine/tests/test_protocol.py`,
// que lee las listas de este archivo.

export const PROTOCOL_VERSION = 1;

export const ENGINE_STATES = ["idle", "listening", "thinking", "speaking"] as const;
export type EngineState = (typeof ENGINE_STATES)[number];

// Qué datos trae cada mensaje del motor.
type ServerPayloads = {
  hello: { engine_version: string };
  state_changed: { state: EngineState };
  transcript_final: { text: string };
  assistant_delta: { text: string };
  // Kronos pide que el usuario apruebe una acción delicada. `summary` dice qué
  // va a hacer («cerrar Spotify»); `detail`, el comando exacto si lo hay.
  confirmation_request: { id: string; summary: string; detail: string };
  // La pregunta se cerró: por voz, con un clic o porque se cortó la conversación.
  confirmation_resolved: { id: string; approved: boolean };
  error: { message: string };
};

export const SERVER_MESSAGES = [
  "hello",
  "state_changed",
  "transcript_final",
  "assistant_delta",
  "confirmation_request",
  "confirmation_resolved",
  "error",
] as const satisfies readonly (keyof ServerPayloads)[];

/** Un mensaje del motor: el tipo decide qué trae `payload`. */
export type ServerMessage = {
  [Type in keyof ServerPayloads]: { v: number; type: Type; payload: ServerPayloads[Type] };
}[keyof ServerPayloads];

// `confirm` y `deny` contestan una confirmación; llevan el `id` de la pregunta.
export const CLIENT_MESSAGES = ["activate", "cancel", "confirm", "deny"] as const;
export type ClientMessage = (typeof CLIENT_MESSAGES)[number];
