import { beforeEach, describe, expect, it, vi } from "vitest";

import { initThemeControls } from "../theme";

function installLocalStorage(): void {
  const store = new Map<string, string>();

  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => store.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => {
        store.set(key, value);
      }),
      removeItem: vi.fn((key: string) => {
        store.delete(key);
      }),
      clear: vi.fn(() => {
        store.clear();
      }),
    },
  });
}

function installMatchMedia(matches: boolean): void {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  });
}

function renderThemeControls(): void {
  document.body.innerHTML = `
    <div class="theme-toggle" role="group" aria-label="Color theme">
      <button type="button" data-theme-option="light"></button>
      <button type="button" data-theme-option="dark"></button>
    </div>
  `;
}

describe("initThemeControls", () => {
  beforeEach(() => {
    installLocalStorage();
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    renderThemeControls();
  });

  it("uses the system theme when no stored preference exists", () => {
    installMatchMedia(true);

    initThemeControls(document, window);

    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("stores and applies a clicked theme preference", () => {
    installMatchMedia(false);

    initThemeControls(document, window);
    const darkButton = document.querySelector<HTMLButtonElement>('[data-theme-option="dark"]');
    darkButton?.click();

    expect(window.localStorage.getItem("semantris-theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(darkButton?.classList.contains("is-active")).toBe(true);
  });
});
