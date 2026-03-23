import type { ErrorResponse, NewGameResponse, StateResponse, TurnResponse } from "./types";

function parseErrorMessage(payload: unknown): string | null {
  if (payload && typeof payload === "object" && "error" in payload) {
    const { error } = payload as ErrorResponse;
    if (typeof error === "string" && error.trim()) {
      return error;
    }
  }

  return null;
}

async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok) {
    throw new Error(parseErrorMessage(payload) ?? "Request failed.");
  }

  return payload as T;
}

export function loadGameState(): Promise<StateResponse> {
  return fetchJson<StateResponse>("/api/game/state");
}

export function createNewGame(): Promise<NewGameResponse> {
  return fetchJson<NewGameResponse>("/api/game/new", {
    method: "POST",
    body: "{}",
  });
}

export function submitClueTurn(clue: string): Promise<TurnResponse> {
  return fetchJson<TurnResponse>("/api/game/turn", {
    method: "POST",
    body: JSON.stringify({ clue }),
  });
}
