const stateRefs = {
  score: document.getElementById("score-value"),
  timer: document.getElementById("timer-value"),
  turns: document.getElementById("turns-value"),
  remaining: document.getElementById("remaining-value"),
  target: document.getElementById("target-value"),
  provider: document.getElementById("provider-badge"),
  latency: document.getElementById("latency-value"),
  progressValue: document.getElementById("progress-value"),
  progressBar: document.getElementById("progress-bar"),
  statusBanner: document.getElementById("status-banner"),
  vocabValue: document.getElementById("vocab-value"),
  lastClueValue: document.getElementById("last-clue-value"),
  tower: document.getElementById("tower"),
  towerStage: document.getElementById("tower-stage"),
  effectsLayer: document.getElementById("effects-layer"),
  clueForm: document.getElementById("clue-form"),
  clueInput: document.getElementById("clue-input"),
  submitButton: document.getElementById("submit-button"),
  newGameButton: document.getElementById("new-game-button"),
};

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const dangerZoneSize = 4;
const animationTimings = {
  miss: 220,
  reorder: 160,
  handoff: 20,
  explode: 120,
  settle: 180,
};

let currentState = null;
let timerHandle = null;
let busy = false;

function formatElapsed(startedAtMs) {
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000));
  const hours = Math.floor(elapsedSeconds / 3600);
  const minutes = Math.floor((elapsedSeconds % 3600) / 60);
  const seconds = elapsedSeconds % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function dangerWordsFromBoard(board) {
  return board.slice(-Math.min(dangerZoneSize, board.length));
}

function setBusy(nextBusy) {
  busy = nextBusy;
  document.body.classList.toggle("is-busy", nextBusy);
  stateRefs.submitButton.disabled = nextBusy || (currentState?.game_over ?? false);
  stateRefs.newGameButton.disabled = nextBusy;
  stateRefs.clueInput.disabled = nextBusy || (currentState?.game_over ?? false);
  stateRefs.submitButton.textContent = nextBusy ? "Routing..." : "Send Clue";
}

function setStatus(message, tone = "neutral") {
  stateRefs.statusBanner.textContent = message;
  stateRefs.statusBanner.className = "status-banner";
  if (tone === "hit") {
    stateRefs.statusBanner.classList.add("is-hit");
  } else if (tone === "miss") {
    stateRefs.statusBanner.classList.add("is-miss");
  } else if (tone === "error") {
    stateRefs.statusBanner.classList.add("is-error");
  }
}

function startTimer(startedAtMs) {
  if (timerHandle) {
    clearInterval(timerHandle);
  }

  stateRefs.timer.textContent = formatElapsed(startedAtMs);
  timerHandle = window.setInterval(() => {
    stateRefs.timer.textContent = formatElapsed(startedAtMs);
  }, 1000);
}

function updateHud(state) {
  currentState = state;

  stateRefs.score.textContent = String(state.score);
  stateRefs.turns.textContent = String(state.turn_count);
  stateRefs.remaining.textContent = String(state.remaining_words);
  stateRefs.target.textContent = state.target_word || "Cleared";
  stateRefs.vocabValue.textContent = state.vocabulary_name;
  stateRefs.lastClueValue.textContent = state.last_clue || "None yet";
  stateRefs.provider.textContent = state.last_provider || "Awaiting clue";
  stateRefs.provider.classList.toggle("is-fallback", Boolean(state.used_fallback));
  stateRefs.latency.textContent = state.last_latency_ms ? `${state.last_latency_ms} ms` : "-- ms";
  stateRefs.progressValue.textContent = `${state.seen_words} / ${state.total_vocabulary} seen`;
  stateRefs.progressBar.style.width = `${(state.seen_words / Math.max(state.total_vocabulary, 1)) * 100}%`;

  startTimer(state.started_at_ms);
  setBusy(false);

  if (state.game_over) {
    setStatus("Run complete. Start a new game to load a fresh tower.", "hit");
    stateRefs.submitButton.textContent = "Run Complete";
    stateRefs.submitButton.disabled = true;
    stateRefs.clueInput.disabled = true;
  }
}

function applyWordClasses(element, word, boardState) {
  const dangerWords = new Set(boardState.danger_zone_words || dangerWordsFromBoard(boardState.board));
  element.className = "word-chip";
  if (dangerWords.has(word)) {
    element.classList.add("word-chip--danger");
  }
  if (boardState.target_word && boardState.target_word === word) {
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

function renderBoard(board, boardState) {
  if (!board.length) {
    stateRefs.tower.innerHTML = '<div class="empty-state">Tower cleared. Start a fresh run.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  board.forEach((word) => {
    fragment.appendChild(createWordElement(word, boardState));
  });
  stateRefs.tower.replaceChildren(fragment);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  return payload;
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function animateBoardTransition(nextBoard, boardState, options = {}) {
  if (prefersReducedMotion) {
    renderBoard(nextBoard, boardState);
    return;
  }

  const duration = options.duration ?? 500;
  const spawnDuration = options.spawnDuration ?? duration;
  const spawnedWords = new Set(options.spawnedWords || []);
  const existingRects = new Map();

  stateRefs.tower.querySelectorAll(".word-chip").forEach((element) => {
    existingRects.set(element.dataset.word, {
      element,
      rect: element.getBoundingClientRect(),
    });
  });

  const fragment = document.createDocumentFragment();
  nextBoard.forEach((word) => {
    const existing = existingRects.get(word);
    const element = existing?.element || createWordElement(word, boardState);
    applyWordClasses(element, word, boardState);
    fragment.appendChild(element);
  });
  stateRefs.tower.replaceChildren(fragment);

  const animations = [];
  stateRefs.tower.querySelectorAll(".word-chip").forEach((element) => {
    const word = element.dataset.word;
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
              { transform: "translate(0, 0)" },
            ],
            {
              duration,
              easing: "cubic-bezier(0.22, 1, 0.36, 1)",
            },
          ).finished.catch(() => undefined),
        );
      }
    } else if (spawnedWords.has(word)) {
      animations.push(
        element.animate(
          [
            { transform: "translateY(-120px) scale(0.94)", opacity: 0 },
            { transform: "translateY(0) scale(1)", opacity: 1 },
          ],
          {
            duration: spawnDuration,
            easing: "cubic-bezier(0.16, 1, 0.3, 1)",
          },
        ).finished.catch(() => undefined),
      );
    }
  });

  if (animations.length) {
    await Promise.all(animations);
  }
}

function spawnBurst(element) {
  const stageRect = stateRefs.towerStage.getBoundingClientRect();
  const rect = element.getBoundingClientRect();
  const burst = document.createElement("span");
  burst.className = "burst";
  burst.style.left = `${rect.left - stageRect.left + rect.width / 2}px`;
  burst.style.top = `${rect.top - stageRect.top + rect.height / 2}px`;
  stateRefs.effectsLayer.appendChild(burst);
  burst.addEventListener("animationend", () => burst.remove(), { once: true });
}

async function explodeWords(wordsToRemove) {
  if (!wordsToRemove.length || prefersReducedMotion) {
    return;
  }

  const animations = [];
  wordsToRemove.forEach((word) => {
    const selector = `[data-word="${CSS.escape(word)}"]`;
    const element = stateRefs.tower.querySelector(selector);
    if (!element) {
      return;
    }

    spawnBurst(element);
    element.classList.add("word-chip--exploding");
    animations.push(
      element.animate(
        [
          { opacity: 1, transform: "scale(1) rotate(0deg)", filter: "blur(0px)" },
          { opacity: 0, transform: "scale(0.78) rotate(-8deg)", filter: "blur(12px)" },
        ],
        {
          duration: animationTimings.explode,
          easing: "cubic-bezier(0.19, 1, 0.22, 1)",
          fill: "forwards",
        },
      ).finished.catch(() => undefined),
    );
  });

  if (animations.length) {
    await Promise.all(animations);
  }
}

function messageWithWarning(result) {
  if (result.state?.last_warning) {
    return `${result.message} ${result.state.last_warning}`;
  }
  return result.message;
}

async function handleTurn(result) {
  const rankedState = {
    ...currentState,
    board: result.ranked_board,
    danger_zone_words: dangerWordsFromBoard(result.ranked_board),
  };

  if (result.resolution === "miss") {
    await animateBoardTransition(result.ranked_board, rankedState, { duration: animationTimings.miss });
    updateHud(result.state);
    setStatus(messageWithWarning(result), "miss");
    return;
  }

  await animateBoardTransition(result.ranked_board, rankedState, { duration: animationTimings.reorder });
  await wait(animationTimings.handoff);
  await explodeWords(result.words_removed);
  await animateBoardTransition(result.new_board, result.state, {
    duration: animationTimings.settle,
    spawnDuration: animationTimings.settle,
    spawnedWords: result.spawned_words,
  });
  updateHud(result.state);
  setStatus(messageWithWarning(result), "hit");
}

async function loadState() {
  const payload = await fetchJson("/api/game/state");
  updateHud(payload.state);
  renderBoard(payload.state.board, payload.state);
  setStatus("Target locked. Transmit a clue and pull it into the strike tray.", "neutral");
}

async function startNewGame() {
  setBusy(true);
  try {
    const payload = await fetchJson("/api/game/new", { method: "POST", body: "{}" });
    updateHud(payload.state);
    renderBoard(payload.state.board, payload.state);
    stateRefs.clueInput.value = "";
    setStatus(payload.message, "neutral");
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
    stateRefs.clueInput.focus();
  }
}

async function submitClue(event) {
  event.preventDefault();
  if (busy || !currentState || currentState.game_over) {
    return;
  }

  const clue = stateRefs.clueInput.value.trim();
  if (!clue) {
    setStatus("Enter a clue before submitting.", "error");
    stateRefs.clueInput.focus();
    return;
  }

  setBusy(true);
  setStatus("Gemini is rethreading the stack around your clue...", "neutral");

  try {
    const result = await fetchJson("/api/game/turn", {
      method: "POST",
      body: JSON.stringify({ clue }),
    });
    await handleTurn(result);
    stateRefs.clueInput.value = "";
  } catch (error) {
    setStatus(error.message, "error");
  } finally {
    setBusy(false);
    stateRefs.clueInput.focus();
  }
}

stateRefs.clueForm.addEventListener("submit", submitClue);
stateRefs.newGameButton.addEventListener("click", startNewGame);

loadState().catch((error) => {
  setStatus(error.message, "error");
});
