import type { ErrorResponse } from "./types";
import type {
  RestrictionStateResponse,
  RestrictionTurnResponse,
} from "./restriction_types";

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

export function loadRestrictionState(): Promise<RestrictionStateResponse> {
  return fetchJson<RestrictionStateResponse>("/api/restriction/state");
}

export function createNewRestrictionGame(): Promise<RestrictionStateResponse & { message: string }> {
  return fetchJson<RestrictionStateResponse & { message: string }>("/api/restriction/new", {
    method: "POST",
    body: "{}",
  });
}

export function submitRestrictionTurn(clue: string): Promise<RestrictionTurnResponse> {
  return fetchJson<RestrictionTurnResponse>("/api/restriction/turn", {
    method: "POST",
    body: JSON.stringify({ clue }),
  });
}
