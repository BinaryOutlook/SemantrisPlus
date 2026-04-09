import { animateBoardTransition, explodeWords } from "./animations";
import { createNewGame, loadGameState, submitClueTurn } from "./api";
import { renderBoard, syncStageMetrics } from "./board";
import type { GameElements } from "./dom";
import { setBusy, setStatus, updateHud } from "./hud";
import { createClientState } from "./state";
import type { TurnResponse } from "./types";
import { buildRankedBoardState, getErrorMessage, messageWithWarning, wait } from "./utils";

const animationTimings = {
  miss: 200,
  reorder: 180,
  handoff: 20,
  explode: 150,
  settle: 200,
} as const;

export function initGameController(elements: GameElements): void {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clientState = createClientState();
  const syncCurrentStageMetrics = (): void => {
    if (!clientState.currentState) {
      return;
    }

    syncStageMetrics(elements, clientState.currentState);
  };

  async function handleTurn(result: TurnResponse): Promise<void> {
    const currentState = clientState.currentState;
    if (!currentState) {
      throw new Error("Game state is not initialized.");
    }

    const rankedState = buildRankedBoardState(currentState, result.ranked_board);

    if (result.resolution === "miss") {
      await animateBoardTransition(
        elements,
        result.ranked_board,
        rankedState,
        { duration: animationTimings.miss },
        prefersReducedMotion
      );
      syncStageMetrics(elements, result.state);
      updateHud(elements, clientState, result.state);
      setStatus(elements, messageWithWarning(result), "miss");
      return;
    }

    await animateBoardTransition(
      elements,
      result.ranked_board,
      rankedState,
      { duration: animationTimings.reorder },
      prefersReducedMotion
    );
    await wait(animationTimings.handoff);
    await explodeWords(
      elements,
      result.words_removed,
      animationTimings.explode,
      prefersReducedMotion
    );
    await animateBoardTransition(
      elements,
      result.new_board,
      result.state,
      {
        duration: animationTimings.settle,
        spawnDuration: animationTimings.settle,
        spawnedWords: result.spawned_words,
      },
      prefersReducedMotion
    );
    syncStageMetrics(elements, result.state);
    updateHud(elements, clientState, result.state);
    setStatus(elements, messageWithWarning(result), "hit");
  }

  async function loadState(): Promise<void> {
    const payload = await loadGameState();
    updateHud(elements, clientState, payload.state);
    renderBoard(elements, payload.state.board, payload.state);
    syncStageMetrics(elements, payload.state);
    if (payload.state.game_over) {
      elements.gameOverNewGameButton.focus();
      return;
    }

    setStatus(elements, "Target ready. Type a clue to pull it toward the clear zone.", "neutral");
  }

  async function startNewGame(): Promise<void> {
    elements.gameOverModal.hidden = true;
    elements.gameOverModal.setAttribute("aria-hidden", "true");
    elements.body.classList.remove("has-game-over-modal");
    setBusy(elements, clientState, true);
    try {
      const payload = await createNewGame();
      updateHud(elements, clientState, payload.state);
      renderBoard(elements, payload.state.board, payload.state);
      syncStageMetrics(elements, payload.state);
      elements.clueInput.value = "";
      setStatus(elements, payload.message, "neutral");
    } catch (error) {
      setStatus(elements, getErrorMessage(error), "error");
    } finally {
      setBusy(elements, clientState, false);
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

    setBusy(elements, clientState, true);
    setStatus(elements, "Ranking the stack around your clue...", "neutral");

    try {
      const result = await submitClueTurn(clue);
      await handleTurn(result);
      elements.clueInput.value = "";
    } catch (error) {
      setStatus(elements, getErrorMessage(error), "error");
    } finally {
      setBusy(elements, clientState, false);
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
  window.addEventListener("resize", syncCurrentStageMetrics);

  if ("fonts" in document) {
    void document.fonts.ready.then(() => {
      syncCurrentStageMetrics();
    });
  }

  void loadState().catch((error) => {
    setStatus(elements, getErrorMessage(error), "error");
  });
}
