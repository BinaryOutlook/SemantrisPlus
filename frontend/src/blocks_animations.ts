import { applyBlocksCellClasses, createBlocksCellElement, renderBlocksGrid } from "./blocks_board";
import type { BlocksElements } from "./blocks_dom";
import type { BlocksCell, BlocksState } from "./blocks_types";

export async function flashPrimaryCell(
  elements: Pick<BlocksElements, "blocksGrid">,
  primaryCell: number,
  duration: number,
  prefersReducedMotion: boolean,
): Promise<void> {
  if (prefersReducedMotion) {
    return;
  }

  const element = elements.blocksGrid.querySelector<HTMLElement>(`[data-cell="${primaryCell}"]`);
  if (!element) {
    return;
  }

  await element
    .animate(
      [
        { transform: "scale(1)", boxShadow: "0 0 0 0 rgba(243, 247, 245, 0.14)" },
        { transform: "scale(1.06)", boxShadow: "0 0 0 10px rgba(243, 247, 245, 0.06)" },
        { transform: "scale(1)", boxShadow: "0 0 0 0 rgba(243, 247, 245, 0)" },
      ],
      {
        duration,
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    )
    .finished.catch(() => undefined);
}

export async function fadeOutBlockCells(
  elements: Pick<BlocksElements, "blocksGrid">,
  removedCells: number[],
  duration: number,
  prefersReducedMotion: boolean,
): Promise<void> {
  if (!removedCells.length || prefersReducedMotion) {
    return;
  }

  const animations = removedCells
    .map((cell) => elements.blocksGrid.querySelector<HTMLElement>(`[data-cell="${cell}"]`))
    .filter((element): element is HTMLElement => Boolean(element))
    .map((element) =>
      element
        .animate(
          [
            { opacity: 1, transform: "scale(1)", filter: "blur(0px)" },
            { opacity: 0, transform: "scale(0.82)", filter: "blur(10px)" },
          ],
          {
            duration,
            easing: "cubic-bezier(0.19, 1, 0.22, 1)",
            fill: "forwards",
          },
        )
        .finished.catch(() => undefined),
    );

  if (animations.length) {
    await Promise.all(animations);
  }
}

export async function animateBlocksGridTransition(
  elements: Pick<BlocksElements, "blocksGrid">,
  nextCells: BlocksCell[],
  state: BlocksState,
  options: {
    spawnedWords?: string[];
    duration?: number;
    spawnDuration?: number;
  } = {},
  prefersReducedMotion: boolean,
): Promise<void> {
  if (prefersReducedMotion) {
    renderBlocksGrid(elements, nextCells, state);
    return;
  }

  const duration = options.duration ?? 260;
  const spawnDuration = options.spawnDuration ?? duration;
  const spawnedWords = new Set(options.spawnedWords ?? []);
  const existingRects = new Map<string, { element: HTMLElement; rect: DOMRect }>();

  elements.blocksGrid.querySelectorAll<HTMLElement>(".blocks-cell--filled").forEach((element) => {
    const word = element.dataset.word;
    if (!word) {
      return;
    }

    existingRects.set(word, {
      element,
      rect: element.getBoundingClientRect(),
    });
  });

  const fragment = document.createDocumentFragment();
  nextCells.forEach((cell) => {
    if (!cell.word) {
      fragment.appendChild(createBlocksCellElement(cell, state));
      return;
    }

    const existing = existingRects.get(cell.word);
    const element = existing?.element ?? createBlocksCellElement(cell, state);
    applyBlocksCellClasses(element, cell, state);
    fragment.appendChild(element);
  });

  elements.blocksGrid.replaceChildren(fragment);

  const animations: Array<Promise<unknown>> = [];
  elements.blocksGrid.querySelectorAll<HTMLElement>(".blocks-cell--filled").forEach((element) => {
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
          element
            .animate(
              [
                { transform: `translate(${deltaX}px, ${deltaY}px)` },
                { transform: "translate(0, 0)" },
              ],
              {
                duration,
                easing: "cubic-bezier(0.22, 1, 0.36, 1)",
              },
            )
            .finished.catch(() => undefined),
        );
      }
    } else if (spawnedWords.has(word)) {
      animations.push(
        element
          .animate(
            [
              { transform: "translateY(-60px) scale(0.9)", opacity: 0 },
              { transform: "translateY(0) scale(1)", opacity: 1 },
            ],
            {
              duration: spawnDuration,
              easing: "cubic-bezier(0.16, 1, 0.3, 1)",
            },
          )
          .finished.catch(() => undefined),
      );
    }
  });

  if (animations.length) {
    await Promise.all(animations);
  }
}
