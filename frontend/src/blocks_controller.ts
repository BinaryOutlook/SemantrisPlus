import { animateBlocksGridTransition, fadeOutBlockCells, flashPrimaryCell } from "./blocks_animations";
import { createNewBlocksGame, loadBlocksState, submitBlocksTurn } from "./blocks_api";
import { renderBlocksGrid } from "./blocks_board";
import type { BlocksElements } from "./blocks_dom";
import type { BlocksState, BlocksTurnResponse } from "./blocks_types";
import { setStatus } from "./hud";
import { formatElapsed, getErrorMessage, messageWithWarning } from "./utils";

interface BlocksClientState {
  currentState: BlocksState | null;
  timerHandle: number | null;
  busy: boolean;
}

const animationTimings = {
  primary: 150,
  explode: 160,
  settle: 240,
} as const;

function createBlocksClientState(): BlocksClientState {
  return {
    currentState: null,
    timerHandle: null,
    busy: false,
  };
}

function setBlocksBusy(
  elements: BlocksElements,
  clientState: BlocksClientState,
  nextBusy: boolean,
): void {
  clientState.busy = nextBusy;
  elements.body.classList.toggle("is-busy", nextBusy);

  const gameOver = clientState.currentState?.game_over ?? false;
  elements.submitButton.disabled = nextBusy || gameOver;
  elements.newGameButton.disabled = nextBusy;
  elements.clueInput.disabled = nextBusy || gameOver;
  elements.submitButton.textContent = nextBusy ? "Resolving..." : "Send Clue";
}

function startTimer(
  elements: Pick<BlocksElements, "timer">,
  clientState: BlocksClientState,
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
  elements: Pick<BlocksElements, "timer">,
  clientState: BlocksClientState,
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
    BlocksElements,
    "body" | "gameOverModal" | "gameOverTitle" | "gameOverMessage"
  >,
  isOpen: boolean,
  title = "You won.",
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

  elements.gameOverTitle.textContent = title;
  elements.gameOverMessage.textContent = message;
}

function updateBlocksHud(
  elements: BlocksElements,
  clientState: BlocksClientState,
  state: BlocksState,
): void {
  clientState.currentState = state;

  elements.score.textContent = String(state.score);
  elements.turns.textContent = String(state.turn_count);
  elements.remaining.textContent = String(state.remaining_words);
  elements.vocabValue.textContent = state.vocabulary_name;
  elements.lastClueValue.textContent = state.last_clue ?? "None yet";
  elements.lastPrimaryValue.textContent = state.last_primary_word ?? "Awaiting clue";
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
  setBlocksBusy(elements, clientState, false);

  if (state.game_over) {
    setStatus(elements, "You cleared the grid. Start a new game to play again.", "hit");
    setGameOverModal(
      elements,
      true,
      state.game_result === "loss" ? "Run over." : "You won.",
      state.game_result === "loss"
        ? `The run ended in ${elements.timer.textContent}. Start a new game to try again.`
        : `You cleared the grid in ${elements.timer.textContent}. Start a new game to play again.`,
    );
    elements.submitButton.textContent = "Run Complete";
    elements.submitButton.disabled = true;
    elements.clueInput.disabled = true;
    return;
  }

  setGameOverModal(elements, false);
}

export function initBlocksController(elements: BlocksElements): void {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clientState = createBlocksClientState();

  async function handleTurn(result: BlocksTurnResponse): Promise<void> {
    await flashPrimaryCell(
      elements,
      result.primary_cell,
      animationTimings.primary,
      prefersReducedMotion,
    );
    await fadeOutBlockCells(
      elements,
      result.removed_cells,
      animationTimings.explode,
      prefersReducedMotion,
    );
    await animateBlocksGridTransition(
      elements,
      result.state.cells,
      result.state,
      {
        duration: animationTimings.settle,
        spawnDuration: animationTimings.settle,
        spawnedWords: result.spawned_words,
      },
      prefersReducedMotion,
    );
    updateBlocksHud(elements, clientState, result.state);
    setStatus(elements, messageWithWarning(result), "hit");
  }

  async function loadState(): Promise<void> {
    const payload = await loadBlocksState();
    updateBlocksHud(elements, clientState, payload.state);
    renderBlocksGrid(elements, payload.state.cells, payload.state);
    if (payload.state.game_over) {
      elements.gameOverNewGameButton.focus();
      return;
    }

    setStatus(elements, "Find an anchor word, trigger a chain, and let gravity reshape the board.", "neutral");
  }

  async function startNewGame(): Promise<void> {
    elements.gameOverModal.hidden = true;
    elements.gameOverModal.setAttribute("aria-hidden", "true");
    elements.body.classList.remove("has-game-over-modal");
    setBlocksBusy(elements, clientState, true);
    try {
      const payload = await createNewBlocksGame();
      updateBlocksHud(elements, clientState, payload.state);
      renderBlocksGrid(elements, payload.state.cells, payload.state);
      elements.clueInput.value = "";
      setStatus(elements, payload.message, "neutral");
    } catch (error) {
      setStatus(elements, getErrorMessage(error), "error");
    } finally {
      setBlocksBusy(elements, clientState, false);
      if (clientState.currentState?.game_over) {
        elements.gameOverNewGameButton.focus();
      } else {
        elements.clueInput.focus();
      }
    }
  }

  async function submitClue(event: Event): Promise<void> {
    event.preventDefault();
    if (clientState.busy || !clientState.currentState || clientState.currentState.game_over) {
      return;
    }

    const clue = elements.clueInput.value.trim();
    if (!clue) {
      setStatus(elements, "Enter a clue before submitting.", "error");
      elements.clueInput.focus();
      return;
    }

    setBlocksBusy(elements, clientState, true);
    setStatus(elements, "Finding a primary hit and resolving the chain...", "neutral");

    try {
      const result = await submitBlocksTurn(clue);
      await handleTurn(result);
      elements.clueInput.value = "";
    } catch (error) {
      setStatus(elements, getErrorMessage(error), "error");
    } finally {
      setBlocksBusy(elements, clientState, false);
      elements.clueInput.focus();
    }
  }

  elements.clueForm.addEventListener("submit", submitClue);
  elements.newGameButton.addEventListener("click", () => {
    void startNewGame();
  });
  elements.gameOverNewGameButton.addEventListener("click", () => {
    void startNewGame();
  });

  void loadState().catch((error) => {
    setStatus(elements, getErrorMessage(error), "error");
  });
}
