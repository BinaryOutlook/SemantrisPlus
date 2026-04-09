import type { GameElements } from "./dom";
import type { BoardState } from "./types";
import { dangerWordsFromBoard } from "./utils";

export function applyWordClasses(element: HTMLElement, word: string, boardState: BoardState): void {
  const dangerWords = new Set(
    boardState.danger_zone_words.length
      ? boardState.danger_zone_words
      : dangerWordsFromBoard(boardState.board, boardState.danger_zone_size)
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
  boardState: BoardState
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

function resolveNumericPixels(value: string): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function syncStageMetrics(
  elements: Pick<GameElements, "tower" | "towerStage" | "dangerZone">,
  boardState: BoardState
): void {
  const dangerRows = Math.max(0, boardState.danger_zone_size);
  const towerStyles = window.getComputedStyle(elements.tower);
  const chip = elements.tower.querySelector<HTMLElement>(".word-chip");
  const chipHeight = chip?.getBoundingClientRect().height ?? 0;
  const rowGap = resolveNumericPixels(towerStyles.rowGap || towerStyles.gap || "0");
  const paddingBottom = resolveNumericPixels(towerStyles.paddingBottom);
  const zoneHeight =
    dangerRows > 0
      ? paddingBottom + chipHeight * dangerRows + rowGap * Math.max(0, dangerRows - 1)
      : 0;

  elements.towerStage.style.setProperty("--danger-zone-height", `${zoneHeight}px`);
  elements.dangerZone.hidden = dangerRows === 0;
}
