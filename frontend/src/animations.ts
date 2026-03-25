import { applyWordClasses, createWordElement, renderBoard } from "./board";
import type { GameElements } from "./dom";
import type { BoardTransitionOptions, BoardState } from "./types";

export async function animateBoardTransition(
  elements: Pick<GameElements, "tower">,
  nextBoard: string[],
  boardState: BoardState,
  options: BoardTransitionOptions = {},
  prefersReducedMotion: boolean,
): Promise<void> {
  if (prefersReducedMotion) {
    renderBoard(elements, nextBoard, boardState);
    return;
  }

  const duration = options.duration ?? 500;
  const spawnDuration = options.spawnDuration ?? duration;
  const spawnedWords = new Set(options.spawnedWords ?? []);
  const spawnFrom = options.spawnFrom ?? "top";
  const existingRects = new Map<string, { element: HTMLElement; rect: DOMRect }>();

  elements.tower.querySelectorAll<HTMLElement>(".word-chip").forEach((element) => {
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
  nextBoard.forEach((word) => {
    const existing = existingRects.get(word);
    const element = existing?.element ?? createWordElement(word, boardState);
    applyWordClasses(element, word, boardState);
    fragment.appendChild(element);
  });
  elements.tower.replaceChildren(fragment);

  const animations: Array<Promise<unknown>> = [];
  elements.tower.querySelectorAll<HTMLElement>(".word-chip").forEach((element) => {
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
      const startTranslate = spawnFrom === "bottom" ? "translateY(120px) scale(0.94)" : "translateY(-120px) scale(0.94)";
      animations.push(
        element
          .animate(
            [
              { transform: startTranslate, opacity: 0 },
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

export function spawnBurst(
  elements: Pick<GameElements, "towerStage" | "effectsLayer">,
  element: HTMLElement,
): void {
  const stageRect = elements.towerStage.getBoundingClientRect();
  const rect = element.getBoundingClientRect();
  const burst = document.createElement("span");
  burst.className = "burst";
  burst.style.left = `${rect.left - stageRect.left + rect.width / 2}px`;
  burst.style.top = `${rect.top - stageRect.top + rect.height / 2}px`;
  elements.effectsLayer.appendChild(burst);
  burst.addEventListener("animationend", () => burst.remove(), { once: true });
}

export async function explodeWords(
  elements: Pick<GameElements, "tower" | "towerStage" | "effectsLayer">,
  wordsToRemove: string[],
  duration: number,
  prefersReducedMotion: boolean,
): Promise<void> {
  if (!wordsToRemove.length || prefersReducedMotion) {
    return;
  }

  const animations: Array<Promise<unknown>> = [];
  wordsToRemove.forEach((word) => {
    const selector = `[data-word="${CSS.escape(word)}"]`;
    const element = elements.tower.querySelector<HTMLElement>(selector);
    if (!element) {
      return;
    }

    spawnBurst(elements, element);
    element.classList.add("word-chip--exploding");
    animations.push(
      element
        .animate(
          [
            { opacity: 1, transform: "scale(1) rotate(0deg)", filter: "blur(0px)" },
            { opacity: 0, transform: "scale(0.78) rotate(-8deg)", filter: "blur(12px)" },
          ],
          {
            duration,
            easing: "cubic-bezier(0.19, 1, 0.22, 1)",
            fill: "forwards",
          },
        )
        .finished.catch(() => undefined),
    );
  });

  if (animations.length) {
    await Promise.all(animations);
  }
}
