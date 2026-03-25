import { describe, expect, it } from "vitest";

import { resolveRestrictionElements } from "../restriction_dom";

function buildRestrictionDocument(): Document {
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
    <div id="active-rule-name"></div>
    <div id="active-rule-description"></div>
    <div id="strike-value"></div>
    <div id="strike-meter"></div>
    <div id="rule-result-value"></div>
  `;

  return document;
}

describe("resolveRestrictionElements", () => {
  it("resolves the base game DOM plus rule-specific elements", () => {
    const documentRef = buildRestrictionDocument();

    const elements = resolveRestrictionElements(documentRef);

    expect(elements.activeRuleName.id).toBe("active-rule-name");
    expect(elements.strikeMeter.id).toBe("strike-meter");
    expect(elements.clueInput.id).toBe("clue-input");
  });
});
