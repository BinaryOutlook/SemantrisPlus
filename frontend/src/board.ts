import type { GameElements } from "./dom";
import type { BoardState } from "./types";
import { dangerWordsFromBoard } from "./utils";

export function applyWordClasses(
  element: HTMLElement,
  word: string,
  boardState: BoardState,
): void {
  const dangerWords = new Set(
    boardState.danger_zone_words.length
      ? boardState.danger_zone_words
      : dangerWordsFromBoard(boardState.board, boardState.danger_zone_size),
  );

  element.className = "word-chip";

  if (dangerWords.has(word)) {
    element.classList.add("word-chip--danger");
  }

  if (boardState.target_word === word) {
    element.classList.add("word-chip--target");
  }
}

export function createWordElement(word: string, boardState: BoardState): HTMLDivElement {
  const element = document.createElement("div");
  element.className = "word-chip";
  element.dataset.word = word;
  element.textContent = word;
  applyWordClasses(element, word, boardState);
  return element;
}

export function renderBoard(
  elements: Pick<GameElements, "tower">,
  board: string[],
  boardState: BoardState,
): void {
  if (!board.length) {
    elements.tower.innerHTML = '<div class="empty-state">Tower cleared. Start a fresh run.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  board.forEach((word) => {
    fragment.appendChild(createWordElement(word, boardState));
  });
  elements.tower.replaceChildren(fragment);
}
