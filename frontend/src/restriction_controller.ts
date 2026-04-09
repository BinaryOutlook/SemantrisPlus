import { animateBoardTransition, explodeWords } from "./animations";
import { renderBoard, syncStageMetrics } from "./board";
import { setBusy, setStatus, updateHud } from "./hud";
import {
  createNewRestrictionGame,
  loadRestrictionState,
  submitRestrictionTurn,
} from "./restriction_api";
import type { RestrictionElements } from "./restriction_dom";
import type { RestrictionState, RestrictionTurnResponse } from "./restriction_types";
import { createClientState } from "./state";
import { buildRankedBoardState, getErrorMessage, messageWithWarning, wait } from "./utils";

const animationTimings = {
  miss: 200,
  reorder: 180,
  handoff: 20,
  explode: 150,
  settle: 200,
  penalty: 220,
} as const;

function renderStrikeMeter(elements: RestrictionElements, state: RestrictionState): void {
  elements.strikeValue.textContent = `${state.strike_count} / ${state.max_strikes}`;
  const fragment = document.createDocumentFragment();
  for (let index = 0; index < state.max_strikes; index += 1) {
    const marker = document.createElement("span");
    marker.className = "restriction-strike";
    if (index < state.strike_count) {
      marker.classList.add("is-filled");
    }
    fragment.appendChild(marker);
  }
  elements.strikeMeter.replaceChildren(fragment);
}

function updateRestrictionHud(
  elements: RestrictionElements,
  clientState: ReturnType<typeof createClientState>,
  state: RestrictionState
): void {
  updateHud(elements, clientState, state);
  elements.activeRuleName.textContent = state.active_rule_name;
  elements.activeRuleDescription.textContent = state.active_rule_description;
  renderStrikeMeter(elements, state);

  if (state.last_rule_passed === null) {
    elements.ruleResultValue.textContent = "Awaiting clue";
    elements.ruleResultValue.className = "status-pill";
  } else {
    elements.ruleResultValue.textContent =
      state.last_rule_reason ?? (state.last_rule_passed ? "Rule passed." : "Rule failed.");
    elements.ruleResultValue.className = "status-pill";
    elements.ruleResultValue.classList.add(
      state.last_rule_passed ? "restriction-pill--pass" : "restriction-pill--fail"
    );
  }

  if (state.game_over && state.game_result === "loss") {
    setStatus(
      elements,
      "The run ended before the tower could be cleared. Start a new game to try again.",
      "error"
    );
  }
}

export function initRestrictionController(elements: RestrictionElements): void {
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clientState = createClientState();
  const syncCurrentStageMetrics = (): void => {
    if (!clientState.currentState) {
      return;
    }

    syncStageMetrics(elements, clientState.currentState);
  };

  async function handleTurn(result: RestrictionTurnResponse): Promise<void> {
    const currentState = clientState.currentState as RestrictionState | null;
    if (!currentState) {
      throw new Error("Game state is not initialized.");
    }

    if (result.resolution === "rule_fail") {
      await animateBoardTransition(
        elements,
        result.new_board,
        result.state,
        {
          duration: animationTimings.penalty,
          spawnDuration: animationTimings.penalty,
          spawnedWords: result.penalty_words,
          spawnFrom: "bottom",
        },
        prefersReducedMotion
      );
      syncStageMetrics(elements, result.state);
      updateRestrictionHud(elements, clientState, result.state);
      setStatus(elements, messageWithWarning(result), "miss");
      return;
    }

    const rankedState = buildRankedBoardState(
      currentState,
      result.ranked_board ?? result.new_board
    );

    if (result.resolution === "miss") {
      await animateBoardTransition(
        elements,
        result.ranked_board ?? result.new_board,
        rankedState,
        { duration: animationTimings.miss },
        prefersReducedMotion
      );
      syncStageMetrics(elements, result.state);
      updateRestrictionHud(elements, clientState, result.state);
      setStatus(elements, messageWithWarning(result), "miss");
      return;
    }

    await animateBoardTransition(
      elements,
      result.ranked_board ?? result.new_board,
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
    updateRestrictionHud(elements, clientState, result.state);
    setStatus(elements, messageWithWarning(result), "hit");
  }

  async function loadState(): Promise<void> {
    const payload = await loadRestrictionState();
    updateRestrictionHud(elements, clientState, payload.state);
    renderBoard(elements, payload.state.board, payload.state);
    syncStageMetrics(elements, payload.state);
    if (payload.state.game_over) {
      elements.gameOverNewGameButton.focus();
      return;
    }

    setStatus(
      elements,
      "Rule locked. Type a clue that satisfies it, then pull the tower into the clear zone.",
      "neutral"
    );
  }

  async function startNewGame(): Promise<void> {
    elements.gameOverModal.hidden = true;
    elements.gameOverModal.setAttribute("aria-hidden", "true");
    elements.body.classList.remove("has-game-over-modal");
    setBusy(elements, clientState, true);
    try {
      const payload = await createNewRestrictionGame();
      updateRestrictionHud(elements, clientState, payload.state);
      renderBoard(elements, payload.state.board, payload.state);
      syncStageMetrics(elements, payload.state);
      elements.clueInput.value = "";
      setStatus(elements, payload.message, "neutral");
    } catch (error) {
      setStatus(elements, getErrorMessage(error), "error");
    } finally {
      setBusy(elements, clientState, false);
      if ((clientState.currentState as RestrictionState | null)?.game_over) {
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
    setStatus(elements, "Checking the active rule and resolving your clue...", "neutral");

    try {
      const result = await submitRestrictionTurn(clue);
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
