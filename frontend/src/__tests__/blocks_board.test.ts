import { describe, expect, it } from "vitest";

import { renderBlocksGrid } from "../blocks_board";
import type { BlocksState } from "../blocks_types";

function buildGridHost(): HTMLElement {
  document.body.innerHTML = `<div id="blocks-grid"></div>`;
  const grid = document.getElementById("blocks-grid");
  if (!grid) {
    throw new Error("Missing blocks grid.");
  }
  return grid;
}

function buildState(): BlocksState {
  return {
    mode_id: "blocks",
    score: 0,
    turn_count: 0,
    started_at_ms: 0,
    ended_at_ms: null,
    last_latency_ms: null,
    last_provider: null,
    used_fallback: false,
    last_warning: null,
    last_clue: null,
    game_over: false,
    game_result: null,
    vocabulary_name: "demo.txt",
    remaining_words: 10,
    seen_words: 4,
    total_vocabulary: 14,
    grid_width: 2,
    grid_height: 2,
    cells: [
      { cell: 0, row: 0, col: 0, word: null },
      { cell: 1, row: 0, col: 1, word: "Anchor" },
      { cell: 2, row: 1, col: 0, word: "Harbor" },
      { cell: 3, row: 1, col: 1, word: null },
    ],
    target_occupied_cells: 2,
    last_primary_word: "Anchor",
    last_primary_cell: 1,
    last_chain_words: ["Anchor", "Harbor"],
    last_chain_size: 2,
    last_scored_cells: [
      { cell: 1, word: "Anchor", score: 100 },
      { cell: 2, word: "Harbor", score: 80 },
    ],
  };
}

describe("renderBlocksGrid", () => {
  it("renders every cell and marks the primary hit", () => {
    const blocksGrid = buildGridHost();
    const state = buildState();

    renderBlocksGrid({ blocksGrid }, state.cells, state);

    expect(blocksGrid.children).toHaveLength(4);
    expect(blocksGrid.querySelectorAll(".blocks-cell--filled")).toHaveLength(2);
    expect(blocksGrid.querySelector(".blocks-cell--primary")?.getAttribute("data-word")).toBe("Anchor");
  });
});
