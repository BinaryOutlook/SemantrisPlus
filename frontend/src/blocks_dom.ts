export interface BlocksElements {
  body: HTMLBodyElement;
  score: HTMLElement;
  timer: HTMLElement;
  turns: HTMLElement;
  remaining: HTMLElement;
  provider: HTMLElement;
  latency: HTMLElement;
  progressValue: HTMLElement;
  progressBar: HTMLElement;
  statusBanner: HTMLElement;
  vocabValue: HTMLElement;
  lastClueValue: HTMLElement;
  lastPrimaryValue: HTMLElement;
  blocksGrid: HTMLElement;
  gameOverModal: HTMLElement;
  gameOverTitle: HTMLElement;
  gameOverMessage: HTMLElement;
  gameOverNewGameButton: HTMLButtonElement;
  clueForm: HTMLFormElement;
  clueInput: HTMLInputElement;
  submitButton: HTMLButtonElement;
  newGameButton: HTMLButtonElement;
}

function requireElement<T extends HTMLElement>(id: string, documentRef: Document): T {
  const element = documentRef.getElementById(id);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing required element: #${id}`);
  }

  return element as T;
}

export function resolveBlocksElements(documentRef: Document = document): BlocksElements {
  if (!(documentRef.body instanceof HTMLBodyElement)) {
    throw new Error("Missing document body.");
  }

  return {
    body: documentRef.body,
    score: requireElement("score-value", documentRef),
    timer: requireElement("timer-value", documentRef),
    turns: requireElement("turns-value", documentRef),
    remaining: requireElement("remaining-value", documentRef),
    provider: requireElement("provider-badge", documentRef),
    latency: requireElement("latency-value", documentRef),
    progressValue: requireElement("progress-value", documentRef),
    progressBar: requireElement("progress-bar", documentRef),
    statusBanner: requireElement("status-banner", documentRef),
    vocabValue: requireElement("vocab-value", documentRef),
    lastClueValue: requireElement("last-clue-value", documentRef),
    lastPrimaryValue: requireElement("last-primary-value", documentRef),
    blocksGrid: requireElement("blocks-grid", documentRef),
    gameOverModal: requireElement("game-over-modal", documentRef),
    gameOverTitle: requireElement("game-over-title", documentRef),
    gameOverMessage: requireElement("game-over-message", documentRef),
    gameOverNewGameButton: requireElement(
      "game-over-new-game-button",
      documentRef
    ) as HTMLButtonElement,
    clueForm: requireElement("clue-form", documentRef) as HTMLFormElement,
    clueInput: requireElement("clue-input", documentRef) as HTMLInputElement,
    submitButton: requireElement("submit-button", documentRef) as HTMLButtonElement,
    newGameButton: requireElement("new-game-button", documentRef) as HTMLButtonElement,
  };
}
