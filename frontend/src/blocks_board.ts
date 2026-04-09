import type { BlocksElements } from "./blocks_dom";
import type { BlocksCell, BlocksState } from "./blocks_types";

export function applyBlocksCellClasses(
  element: HTMLElement,
  cell: BlocksCell,
  state: BlocksState
): void {
  element.className = "blocks-cell";
  element.dataset.cell = String(cell.cell);
  element.style.setProperty("--blocks-col", String(cell.col + 1));
  element.style.setProperty("--blocks-row", String(cell.row + 1));

  if (!cell.word) {
    element.classList.add("blocks-cell--empty");
    element.removeAttribute("data-word");
    element.textContent = "";
    return;
  }

  element.classList.add("blocks-cell--filled");
  element.dataset.word = cell.word;
  element.textContent = cell.word;

  if (state.last_primary_cell === cell.cell) {
    element.classList.add("blocks-cell--primary");
  }

  if (state.last_scored_cells.some((item) => item.cell === cell.cell && item.score >= 75)) {
    element.classList.add("blocks-cell--combo");
  }
}

export function createBlocksCellElement(cell: BlocksCell, state: BlocksState): HTMLDivElement {
  const element = document.createElement("div");
  applyBlocksCellClasses(element, cell, state);
  return element;
}

export function renderBlocksGrid(
  elements: Pick<BlocksElements, "blocksGrid">,
  cells: BlocksCell[],
  state: BlocksState
): void {
  elements.blocksGrid.style.setProperty("--blocks-columns", String(state.grid_width));
  elements.blocksGrid.style.setProperty("--blocks-rows", String(state.grid_height));

  const fragment = document.createDocumentFragment();
  cells.forEach((cell) => {
    fragment.appendChild(createBlocksCellElement(cell, state));
  });
  elements.blocksGrid.replaceChildren(fragment);
}
