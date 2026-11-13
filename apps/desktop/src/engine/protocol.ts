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
  error: { message: string };
};

export const SERVER_MESSAGES = [
  "hello",
  "state_changed",
  "transcript_final",
  "assistant_delta",
  "error",
] as const satisfies readonly (keyof ServerPayloads)[];

/** Un mensaje del motor: el tipo decide qué trae `payload`. */
export type ServerMessage = {
  [Type in keyof ServerPayloads]: { v: number; type: Type; payload: ServerPayloads[Type] };
}[keyof ServerPayloads];

export const CLIENT_MESSAGES = ["activate", "cancel"] as const;
export type ClientMessage = (typeof CLIENT_MESSAGES)[number];
