import { describe, expect, it, vi } from "vitest";

import { syncStageMetrics } from "../board";

function buildStage(): {
  tower: HTMLElement;
  towerStage: HTMLElement;
  dangerZone: HTMLElement;
  chip: HTMLElement;
} {
  document.body.innerHTML = `
    <div id="tower-stage">
      <div id="danger-zone"></div>
      <div id="tower"></div>
    </div>
  `;

  const tower = document.getElementById("tower");
  const towerStage = document.getElementById("tower-stage");
  const dangerZone = document.getElementById("danger-zone");

  if (!tower || !towerStage || !dangerZone) {
    throw new Error("Failed to build test stage.");
  }

  tower.style.display = "flex";
  tower.style.flexDirection = "column";
  tower.style.gap = "8px";
  tower.style.paddingBottom = "20px";

  const chip = document.createElement("div");
  chip.className = "word-chip";
  vi.spyOn(chip, "getBoundingClientRect").mockReturnValue({
    width: 200,
    height: 36,
    top: 0,
    right: 200,
    bottom: 36,
    left: 0,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  } as DOMRect);
  tower.appendChild(chip);

  return { tower, towerStage, dangerZone, chip };
}

describe("syncStageMetrics", () => {
  it("sets the clear-zone height from rendered chip geometry", () => {
    const { tower, towerStage, dangerZone } = buildStage();

    syncStageMetrics(
      { tower, towerStage, dangerZone },
      {
        board: ["a", "b", "c", "d", "e"],
        danger_zone_size: 4,
        danger_zone_words: ["b", "c", "d", "e"],
        target_word: "c",
      }
    );

    expect(towerStage.style.getPropertyValue("--danger-zone-height")).toBe("188px");
    expect(dangerZone.hidden).toBe(false);
  });

  it("hides the clear zone when there are no danger rows", () => {
    const { tower, towerStage, dangerZone } = buildStage();

    syncStageMetrics(
      { tower, towerStage, dangerZone },
      {
        board: [],
        danger_zone_size: 0,
        danger_zone_words: [],
        target_word: null,
      }
    );

    expect(towerStage.style.getPropertyValue("--danger-zone-height")).toBe("0px");
    expect(dangerZone.hidden).toBe(true);
  });
});
