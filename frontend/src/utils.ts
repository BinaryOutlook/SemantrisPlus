import type { GameState } from "./types";

export function formatElapsed(startedAtMs: number, nowMs = Date.now()): string {
  const elapsedSeconds = Math.max(0, Math.floor((nowMs - startedAtMs) / 1000));
  const hours = Math.floor(elapsedSeconds / 3600);
  const minutes = Math.floor((elapsedSeconds % 3600) / 60);
  const seconds = elapsedSeconds % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

export function dangerWordsFromBoard(board: string[], dangerZoneSize: number): string[] {
  return board.slice(-Math.min(dangerZoneSize, board.length));
}

export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "Request failed.";
}

export function messageWithWarning(result: {
  message: string;
  state: {
    last_warning: string | null;
  };
}): string {
  if (result.state.last_warning) {
    return `${result.message} ${result.state.last_warning}`;
  }

  return result.message;
}

export function buildRankedBoardState(currentState: GameState, rankedBoard: string[]): GameState {
  return {
    ...currentState,
    board: rankedBoard,
    danger_zone_words: dangerWordsFromBoard(rankedBoard, currentState.danger_zone_size),
  };
}
