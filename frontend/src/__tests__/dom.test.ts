import { describe, expect, it } from "vitest";

import { resolveGameElements } from "../dom";

function buildGameDocument(): Document {
  document.body.innerHTML = `
    <strong id="score-value"></strong>
    <strong id="timer-value"></strong>
    <strong id="turns-value"></strong>
    <strong id="remaining-value"></strong>
    <div id="target-value"></div>
    <span id="provider-badge"></span>
    <span id="latency-value"></span>
    <span id="progress-value"></span>
    <div id="progress-bar"></div>
    <div id="status-banner"></div>
    <dd id="vocab-value"></dd>
    <dd id="last-clue-value"></dd>
    <div id="tower"></div>
    <div id="tower-stage"></div>
    <div id="danger-zone"></div>
    <div id="effects-layer"></div>
    <div id="game-over-modal"></div>
    <h2 id="game-over-title"></h2>
    <p id="game-over-message"></p>
    <button id="game-over-new-game-button"></button>
    <form id="clue-form"></form>
    <input id="clue-input" />
    <button id="submit-button"></button>
    <button id="new-game-button"></button>
  `;

  return document;
}

describe("resolveGameElements", () => {
  it("resolves all required DOM references", () => {
    const documentRef = buildGameDocument();

    const elements = resolveGameElements(documentRef);

    expect(elements.clueInput.id).toBe("clue-input");
    expect(elements.submitButton.id).toBe("submit-button");
    expect(elements.tower.id).toBe("tower");
    expect(elements.gameOverNewGameButton.id).toBe("game-over-new-game-button");
  });

  it("throws when a required element is missing", () => {
    document.body.innerHTML = `<div id="score-value"></div>`;

    expect(() => resolveGameElements(document)).toThrow("Missing required element");
  });
});
