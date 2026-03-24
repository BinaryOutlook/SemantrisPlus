"use strict";
(() => {
  // frontend/src/api.ts
  function parseErrorMessage(payload) {
    if (payload && typeof payload === "object" && "error" in payload) {
      const { error } = payload;
      if (typeof error === "string" && error.trim()) {
        return error;
      }
    }
    return null;
  }
  async function fetchJson(url, options = {}) {
    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers ?? {}
      },
      ...options
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      throw new Error(parseErrorMessage(payload) ?? "Request failed.");
    }
    return payload;
  }
  function loadGameState() {
    return fetchJson("/api/game/state");
  }
  function createNewGame() {
    return fetchJson("/api/game/new", {
      method: "POST",
      body: "{}"
    });
  }
  function submitClueTurn(clue) {
    return fetchJson("/api/game/turn", {
      method: "POST",
      body: JSON.stringify({ clue })
    });
  }

  // frontend/src/utils.ts
  function formatElapsed(startedAtMs, nowMs = Date.now()) {
    const elapsedSeconds = Math.max(0, Math.floor((nowMs - startedAtMs) / 1e3));
    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor(elapsedSeconds % 3600 / 60);
    const seconds = elapsedSeconds % 60;
    if (hours > 0) {
      return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  function dangerWordsFromBoard(board, dangerZoneSize) {
    return board.slice(-Math.min(dangerZoneSize, board.length));
  }
  function wait(ms) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, ms);
    });
  }
  function getErrorMessage(error) {
    if (error instanceof Error && error.message) {
      return error.message;
    }
    return "Request failed.";
  }
  function messageWithWarning(result) {
    if (result.state.last_warning) {
      return `${result.message} ${result.state.last_warning}`;
    }
    return result.message;
  }
  function buildRankedBoardState(currentState, rankedBoard) {
    return {
      ...currentState,
      board: rankedBoard,
      danger_zone_words: dangerWordsFromBoard(rankedBoard, currentState.danger_zone_size)
    };
  }

  // frontend/src/board.ts
  function applyWordClasses(element, word, boardState) {
    const dangerWords = new Set(
      boardState.danger_zone_words.length ? boardState.danger_zone_words : dangerWordsFromBoard(boardState.board, boardState.danger_zone_size)
    );
    element.className = "word-chip";
    if (dangerWords.has(word)) {
      element.classList.add("word-chip--danger");
    }
    if (boardState.target_word === word) {
      element.classList.add("word-chip--target");
    }
  }
  function createWordElement(word, boardState) {
    const element = document.createElement("div");
    element.className = "word-chip";
    element.dataset.word = word;
    element.textContent = word;
    applyWordClasses(element, word, boardState);
    return element;
  }
  function renderBoard(elements2, board, boardState) {
    if (!board.length) {
      elements2.tower.innerHTML = '<div class="empty-state">Tower cleared. Start a fresh run.</div>';
      return;
    }
    const fragment = document.createDocumentFragment();
    board.forEach((word) => {
      fragment.appendChild(createWordElement(word, boardState));
    });
    elements2.tower.replaceChildren(fragment);
  }
  function resolveNumericPixels(value) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  function syncStageMetrics(elements2, boardState) {
    const dangerRows = Math.max(0, boardState.danger_zone_size);
    const towerStyles = window.getComputedStyle(elements2.tower);
    const chip = elements2.tower.querySelector(".word-chip");
    const chipHeight = chip?.getBoundingClientRect().height ?? 0;
    const rowGap = resolveNumericPixels(towerStyles.rowGap || towerStyles.gap || "0");
    const paddingBottom = resolveNumericPixels(towerStyles.paddingBottom);
    const zoneHeight = dangerRows > 0 ? paddingBottom + chipHeight * dangerRows + rowGap * Math.max(0, dangerRows - 1) : 0;
    elements2.towerStage.style.setProperty("--danger-zone-height", `${zoneHeight}px`);
    elements2.dangerZone.hidden = dangerRows === 0;
  }

  // frontend/src/animations.ts
  async function animateBoardTransition(elements2, nextBoard, boardState, options = {}, prefersReducedMotion) {
    if (prefersReducedMotion) {
      renderBoard(elements2, nextBoard, boardState);
      return;
    }
    const duration = options.duration ?? 500;
    const spawnDuration = options.spawnDuration ?? duration;
    const spawnedWords = new Set(options.spawnedWords ?? []);
    const existingRects = /* @__PURE__ */ new Map();
    elements2.tower.querySelectorAll(".word-chip").forEach((element) => {
      const word = element.dataset.word;
      if (!word) {
        return;
      }
      existingRects.set(word, {
        element,
        rect: element.getBoundingClientRect()
      });
    });
    const fragment = document.createDocumentFragment();
    nextBoard.forEach((word) => {
      const existing = existingRects.get(word);
      const element = existing?.element ?? createWordElement(word, boardState);
      applyWordClasses(element, word, boardState);
      fragment.appendChild(element);
    });
    elements2.tower.replaceChildren(fragment);
    const animations = [];
    elements2.tower.querySelectorAll(".word-chip").forEach((element) => {
      const word = element.dataset.word;
      if (!word) {
        return;
      }
      const first = existingRects.get(word)?.rect;
      const last = element.getBoundingClientRect();
      if (first) {
        const deltaX = first.left - last.left;
        const deltaY = first.top - last.top;
        if (Math.abs(deltaX) > 1 || Math.abs(deltaY) > 1) {
          animations.push(
            element.animate(
              [
                { transform: `translate(${deltaX}px, ${deltaY}px)` },
                { transform: "translate(0, 0)" }
              ],
              {
                duration,
                easing: "cubic-bezier(0.22, 1, 0.36, 1)"
              }
            ).finished.catch(() => void 0)
          );
        }
      } else if (spawnedWords.has(word)) {
        animations.push(
          element.animate(
            [
              { transform: "translateY(-120px) scale(0.94)", opacity: 0 },
              { transform: "translateY(0) scale(1)", opacity: 1 }
            ],
            {
              duration: spawnDuration,
              easing: "cubic-bezier(0.16, 1, 0.3, 1)"
            }
          ).finished.catch(() => void 0)
        );
      }
    });
    if (animations.length) {
      await Promise.all(animations);
    }
  }
  function spawnBurst(elements2, element) {
    const stageRect = elements2.towerStage.getBoundingClientRect();
    const rect = element.getBoundingClientRect();
    const burst = document.createElement("span");
    burst.className = "burst";
    burst.style.left = `${rect.left - stageRect.left + rect.width / 2}px`;
    burst.style.top = `${rect.top - stageRect.top + rect.height / 2}px`;
    elements2.effectsLayer.appendChild(burst);
    burst.addEventListener("animationend", () => burst.remove(), { once: true });
  }
  async function explodeWords(elements2, wordsToRemove, duration, prefersReducedMotion) {
    if (!wordsToRemove.length || prefersReducedMotion) {
      return;
    }
    const animations = [];
    wordsToRemove.forEach((word) => {
      const selector = `[data-word="${CSS.escape(word)}"]`;
      const element = elements2.tower.querySelector(selector);
      if (!element) {
        return;
      }
      spawnBurst(elements2, element);
      element.classList.add("word-chip--exploding");
      animations.push(
        element.animate(
          [
            { opacity: 1, transform: "scale(1) rotate(0deg)", filter: "blur(0px)" },
            { opacity: 0, transform: "scale(0.78) rotate(-8deg)", filter: "blur(12px)" }
          ],
          {
            duration,
            easing: "cubic-bezier(0.19, 1, 0.22, 1)",
            fill: "forwards"
          }
        ).finished.catch(() => void 0)
      );
    });
    if (animations.length) {
      await Promise.all(animations);
    }
  }

  // frontend/src/hud.ts
  function setBusy(elements2, clientState, nextBusy) {
    clientState.busy = nextBusy;
    elements2.body.classList.toggle("is-busy", nextBusy);
    const gameOver = clientState.currentState?.game_over ?? false;
    elements2.submitButton.disabled = nextBusy || gameOver;
    elements2.newGameButton.disabled = nextBusy;
    elements2.clueInput.disabled = nextBusy || gameOver;
    elements2.submitButton.textContent = nextBusy ? "Ranking..." : "Send Clue";
  }
  function setStatus(elements2, message, tone = "neutral") {
    elements2.statusBanner.textContent = message;
    elements2.statusBanner.className = "status-banner";
    if (tone === "hit") {
      elements2.statusBanner.classList.add("is-hit");
    } else if (tone === "miss") {
      elements2.statusBanner.classList.add("is-miss");
    } else if (tone === "error") {
      elements2.statusBanner.classList.add("is-error");
    }
  }
  function startTimer(elements2, clientState, startedAtMs) {
    if (clientState.timerHandle !== null) {
      window.clearInterval(clientState.timerHandle);
    }
    elements2.timer.textContent = formatElapsed(startedAtMs);
    clientState.timerHandle = window.setInterval(() => {
      elements2.timer.textContent = formatElapsed(startedAtMs);
    }, 1e3);
  }
  function stopTimer(elements2, clientState, startedAtMs, endedAtMs) {
    if (clientState.timerHandle !== null) {
      window.clearInterval(clientState.timerHandle);
      clientState.timerHandle = null;
    }
    elements2.timer.textContent = formatElapsed(startedAtMs, endedAtMs ?? Date.now());
  }
  function setGameOverModal(elements2, isOpen, message = "") {
    elements2.body.classList.toggle("has-game-over-modal", isOpen);
    elements2.gameOverModal.hidden = !isOpen;
    elements2.gameOverModal.setAttribute("aria-hidden", String(!isOpen));
    if (!isOpen) {
      elements2.gameOverTitle.textContent = "You won.";
      elements2.gameOverMessage.textContent = "";
      return;
    }
    elements2.gameOverTitle.textContent = "You won.";
    elements2.gameOverMessage.textContent = message;
  }
  function updateHud(elements2, clientState, state) {
    clientState.currentState = state;
    elements2.score.textContent = String(state.score);
    elements2.turns.textContent = String(state.turn_count);
    elements2.remaining.textContent = String(state.remaining_words);
    elements2.target.textContent = state.target_word ?? "Cleared";
    elements2.vocabValue.textContent = state.vocabulary_name;
    elements2.lastClueValue.textContent = state.last_clue ?? "None yet";
    elements2.provider.textContent = state.last_provider ?? "Awaiting clue";
    elements2.provider.classList.toggle("is-fallback", Boolean(state.used_fallback));
    elements2.latency.textContent = state.last_latency_ms ? `${state.last_latency_ms} ms` : "-- ms";
    elements2.progressValue.textContent = `${state.seen_words} / ${state.total_vocabulary} seen`;
    elements2.progressBar.style.width = `${state.seen_words / Math.max(state.total_vocabulary, 1) * 100}%`;
    if (state.game_over) {
      stopTimer(elements2, clientState, state.started_at_ms, state.ended_at_ms);
    } else {
      startTimer(elements2, clientState, state.started_at_ms);
    }
    setBusy(elements2, clientState, false);
    if (state.game_over) {
      setStatus(elements2, "You cleared the tower. Start a new game to play again.", "hit");
      setGameOverModal(
        elements2,
        true,
        `You cleared the tower in ${elements2.timer.textContent}. Start a new game to play again.`
      );
      elements2.submitButton.textContent = "Run Complete";
      elements2.submitButton.disabled = true;
      elements2.clueInput.disabled = true;
      return;
    }
    setGameOverModal(elements2, false);
  }

  // frontend/src/state.ts
  function createClientState() {
    return {
      currentState: null,
      timerHandle: null,
      busy: false
    };
  }

  // frontend/src/controller.ts
  var animationTimings = {
    miss: 200,
    reorder: 180,
    handoff: 20,
    explode: 150,
    settle: 200
  };
  function initGameController(elements2) {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const clientState = createClientState();
    const syncCurrentStageMetrics = () => {
      if (!clientState.currentState) {
        return;
      }
      syncStageMetrics(elements2, clientState.currentState);
    };
    async function handleTurn(result) {
      const currentState = clientState.currentState;
      if (!currentState) {
        throw new Error("Game state is not initialized.");
      }
      const rankedState = buildRankedBoardState(currentState, result.ranked_board);
      if (result.resolution === "miss") {
        await animateBoardTransition(
          elements2,
          result.ranked_board,
          rankedState,
          { duration: animationTimings.miss },
          prefersReducedMotion
        );
        syncStageMetrics(elements2, result.state);
        updateHud(elements2, clientState, result.state);
        setStatus(elements2, messageWithWarning(result), "miss");
        return;
      }
      await animateBoardTransition(
        elements2,
        result.ranked_board,
        rankedState,
        { duration: animationTimings.reorder },
        prefersReducedMotion
      );
      await wait(animationTimings.handoff);
      await explodeWords(elements2, result.words_removed, animationTimings.explode, prefersReducedMotion);
      await animateBoardTransition(
        elements2,
        result.new_board,
        result.state,
        {
          duration: animationTimings.settle,
          spawnDuration: animationTimings.settle,
          spawnedWords: result.spawned_words
        },
        prefersReducedMotion
      );
      syncStageMetrics(elements2, result.state);
      updateHud(elements2, clientState, result.state);
      setStatus(elements2, messageWithWarning(result), "hit");
    }
    async function loadState() {
      const payload = await loadGameState();
      updateHud(elements2, clientState, payload.state);
      renderBoard(elements2, payload.state.board, payload.state);
      syncStageMetrics(elements2, payload.state);
      if (payload.state.game_over) {
        elements2.gameOverNewGameButton.focus();
        return;
      }
      setStatus(elements2, "Target ready. Type a clue to pull it toward the clear zone.", "neutral");
    }
    async function startNewGame() {
      elements2.gameOverModal.hidden = true;
      elements2.gameOverModal.setAttribute("aria-hidden", "true");
      elements2.body.classList.remove("has-game-over-modal");
      setBusy(elements2, clientState, true);
      try {
        const payload = await createNewGame();
        updateHud(elements2, clientState, payload.state);
        renderBoard(elements2, payload.state.board, payload.state);
        syncStageMetrics(elements2, payload.state);
        elements2.clueInput.value = "";
        setStatus(elements2, payload.message, "neutral");
      } catch (error) {
        setStatus(elements2, getErrorMessage(error), "error");
      } finally {
        setBusy(elements2, clientState, false);
        if (clientState.currentState?.game_over) {
          elements2.gameOverNewGameButton.focus();
        } else {
          elements2.clueInput.focus();
        }
      }
    }
    async function submitClue(event) {
      event.preventDefault();
      if (clientState.busy || !clientState.currentState || clientState.currentState.game_over) {
        return;
      }
      const clue = elements2.clueInput.value.trim();
      if (!clue) {
        setStatus(elements2, "Enter a clue before submitting.", "error");
        elements2.clueInput.focus();
        return;
      }
      setBusy(elements2, clientState, true);
      setStatus(elements2, "Ranking the stack around your clue...", "neutral");
      try {
        const result = await submitClueTurn(clue);
        await handleTurn(result);
        elements2.clueInput.value = "";
      } catch (error) {
        setStatus(elements2, getErrorMessage(error), "error");
      } finally {
        setBusy(elements2, clientState, false);
        elements2.clueInput.focus();
      }
    }
    elements2.clueForm.addEventListener("submit", submitClue);
    elements2.newGameButton.addEventListener("click", () => {
      void startNewGame();
    });
    elements2.gameOverNewGameButton.addEventListener("click", () => {
      void startNewGame();
    });
    window.addEventListener("resize", syncCurrentStageMetrics);
    if ("fonts" in document) {
      void document.fonts.ready.then(() => {
        syncCurrentStageMetrics();
      });
    }
    void loadState().catch((error) => {
      setStatus(elements2, getErrorMessage(error), "error");
    });
  }

  // frontend/src/dom.ts
  function requireElement(id, documentRef) {
    const element = documentRef.getElementById(id);
    if (!(element instanceof HTMLElement)) {
      throw new Error(`Missing required element: #${id}`);
    }
    return element;
  }
  function resolveGameElements(documentRef = document) {
    if (!(documentRef.body instanceof HTMLBodyElement)) {
      throw new Error("Missing document body.");
    }
    return {
      body: documentRef.body,
      score: requireElement("score-value", documentRef),
      timer: requireElement("timer-value", documentRef),
      turns: requireElement("turns-value", documentRef),
      remaining: requireElement("remaining-value", documentRef),
      target: requireElement("target-value", documentRef),
      provider: requireElement("provider-badge", documentRef),
      latency: requireElement("latency-value", documentRef),
      progressValue: requireElement("progress-value", documentRef),
      progressBar: requireElement("progress-bar", documentRef),
      statusBanner: requireElement("status-banner", documentRef),
      vocabValue: requireElement("vocab-value", documentRef),
      lastClueValue: requireElement("last-clue-value", documentRef),
      tower: requireElement("tower", documentRef),
      towerStage: requireElement("tower-stage", documentRef),
      dangerZone: requireElement("danger-zone", documentRef),
      effectsLayer: requireElement("effects-layer", documentRef),
      gameOverModal: requireElement("game-over-modal", documentRef),
      gameOverTitle: requireElement("game-over-title", documentRef),
      gameOverMessage: requireElement("game-over-message", documentRef),
      gameOverNewGameButton: requireElement("game-over-new-game-button", documentRef),
      clueForm: requireElement("clue-form", documentRef),
      clueInput: requireElement("clue-input", documentRef),
      submitButton: requireElement("submit-button", documentRef),
      newGameButton: requireElement("new-game-button", documentRef)
    };
  }

  // frontend/src/game.ts
  var elements = resolveGameElements();
  initGameController(elements);
})();
//# sourceMappingURL=game.bundle.js.map
