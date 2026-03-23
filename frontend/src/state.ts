import type { GameState } from "./types";

export interface ClientState {
  currentState: GameState | null;
  timerHandle: number | null;
  busy: boolean;
}

export function createClientState(): ClientState {
  return {
    currentState: null,
    timerHandle: null,
    busy: false,
  };
}
