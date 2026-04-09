import type { BlocksStateResponse, BlocksTurnResponse } from "./blocks_types";
import type { ErrorResponse } from "./types";

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

export function loadBlocksState(): Promise<BlocksStateResponse> {
  return fetchJson<BlocksStateResponse>("/api/blocks/state");
}

export function createNewBlocksGame(): Promise<BlocksStateResponse & { message: string }> {
  return fetchJson<BlocksStateResponse & { message: string }>("/api/blocks/new", {
    method: "POST",
    body: "{}",
  });
}

export function submitBlocksTurn(clue: string): Promise<BlocksTurnResponse> {
  return fetchJson<BlocksTurnResponse>("/api/blocks/turn", {
    method: "POST",
    body: JSON.stringify({ clue }),
  });
}
