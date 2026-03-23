import type { GameElements } from "./dom";
import type { ClientState } from "./state";
import type { GameState, StatusTone } from "./types";
import { formatElapsed } from "./utils";

export function setBusy(
  elements: GameElements,
  clientState: ClientState,
  nextBusy: boolean,
): void {
  clientState.busy = nextBusy;
  elements.body.classList.toggle("is-busy", nextBusy);

  const gameOver = clientState.currentState?.game_over ?? false;
  elements.submitButton.disabled = nextBusy || gameOver;
  elements.newGameButton.disabled = nextBusy;
  elements.clueInput.disabled = nextBusy || gameOver;
  elements.submitButton.textContent = nextBusy ? "Ranking..." : "Send Clue";
}

export function setStatus(
  elements: Pick<GameElements, "statusBanner">,
  message: string,
  tone: StatusTone = "neutral",
): void {
  elements.statusBanner.textContent = message;
  elements.statusBanner.className = "status-banner";

  if (tone === "hit") {
    elements.statusBanner.classList.add("is-hit");
  } else if (tone === "miss") {
    elements.statusBanner.classList.add("is-miss");
  } else if (tone === "error") {
    elements.statusBanner.classList.add("is-error");
  }
}

function startTimer(
  elements: Pick<GameElements, "timer">,
  clientState: ClientState,
  startedAtMs: number,
): void {
  if (clientState.timerHandle !== null) {
    window.clearInterval(clientState.timerHandle);
  }

  elements.timer.textContent = formatElapsed(startedAtMs);
  clientState.timerHandle = window.setInterval(() => {
    elements.timer.textContent = formatElapsed(startedAtMs);
  }, 1000);
}

function stopTimer(
  elements: Pick<GameElements, "timer">,
  clientState: ClientState,
  startedAtMs: number,
  endedAtMs: number | null,
): void {
  if (clientState.timerHandle !== null) {
    window.clearInterval(clientState.timerHandle);
    clientState.timerHandle = null;
  }

  elements.timer.textContent = formatElapsed(startedAtMs, endedAtMs ?? Date.now());
}

function setGameOverModal(
  elements: Pick<
    GameElements,
    "body" | "gameOverModal" | "gameOverTitle" | "gameOverMessage"
  >,
  isOpen: boolean,
  message = "",
): void {
  elements.body.classList.toggle("has-game-over-modal", isOpen);
  elements.gameOverModal.hidden = !isOpen;
  elements.gameOverModal.setAttribute("aria-hidden", String(!isOpen));

  if (!isOpen) {
    elements.gameOverTitle.textContent = "You won.";
    elements.gameOverMessage.textContent = "";
    return;
  }

  elements.gameOverTitle.textContent = "You won.";
  elements.gameOverMessage.textContent = message;
}

export function updateHud(
  elements: GameElements,
  clientState: ClientState,
  state: GameState,
): void {
  clientState.currentState = state;

  elements.score.textContent = String(state.score);
  elements.turns.textContent = String(state.turn_count);
  elements.remaining.textContent = String(state.remaining_words);
  elements.target.textContent = state.target_word ?? "Cleared";
  elements.vocabValue.textContent = state.vocabulary_name;
  elements.lastClueValue.textContent = state.last_clue ?? "None yet";
  elements.provider.textContent = state.last_provider ?? "Awaiting clue";
  elements.provider.classList.toggle("is-fallback", Boolean(state.used_fallback));
  elements.latency.textContent = state.last_latency_ms ? `${state.last_latency_ms} ms` : "-- ms";
  elements.progressValue.textContent = `${state.seen_words} / ${state.total_vocabulary} seen`;
  elements.progressBar.style.width = `${(state.seen_words / Math.max(state.total_vocabulary, 1)) * 100}%`;

  if (state.game_over) {
    stopTimer(elements, clientState, state.started_at_ms, state.ended_at_ms);
  } else {
    startTimer(elements, clientState, state.started_at_ms);
  }
  setBusy(elements, clientState, false);

  if (state.game_over) {
    setStatus(elements, "You cleared the tower. Start a new game to play again.", "hit");
    setGameOverModal(
      elements,
      true,
      `You cleared the tower in ${elements.timer.textContent}. Start a new game to play again.`,
    );
    elements.submitButton.textContent = "Run Complete";
    elements.submitButton.disabled = true;
    elements.clueInput.disabled = true;
    return;
  }

  setGameOverModal(elements, false);
}
