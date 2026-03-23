import { describe, expect, it } from "vitest";

import { dangerWordsFromBoard, formatElapsed } from "../utils";

describe("formatElapsed", () => {
  it("formats durations under an hour as mm:ss", () => {
    expect(formatElapsed(0, 61_000)).toBe("01:01");
  });

  it("formats durations over an hour as hh:mm:ss", () => {
    expect(formatElapsed(0, 3_661_000)).toBe("01:01:01");
  });
});

describe("dangerWordsFromBoard", () => {
  it("returns the trailing danger-zone words", () => {
    expect(dangerWordsFromBoard(["A", "B", "C", "D", "E"], 4)).toEqual(["B", "C", "D", "E"]);
  });

  it("caps the slice at the board length", () => {
    expect(dangerWordsFromBoard(["A", "B"], 4)).toEqual(["A", "B"]);
  });
});
