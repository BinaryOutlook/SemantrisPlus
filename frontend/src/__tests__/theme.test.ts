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
      <button type="button" data-theme-option="cupertino"></button>
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
    const cupertinoButton = document.querySelector<HTMLButtonElement>(
      '[data-theme-option="cupertino"]',
    );
    cupertinoButton?.click();

    expect(window.localStorage.getItem("semantris-theme")).toBe("cupertino");
    expect(document.documentElement.dataset.theme).toBe("cupertino");
    expect(cupertinoButton?.classList.contains("is-active")).toBe(true);
  });

  it("uses a stored cupertino preference instead of the system theme", () => {
    installMatchMedia(true);
    window.localStorage.setItem("semantris-theme", "cupertino");

    initThemeControls(document, window);

    expect(document.documentElement.dataset.theme).toBe("cupertino");
  });

  it("ignores invalid stored values and falls back to the system theme", () => {
    installMatchMedia(false);
    window.localStorage.setItem("semantris-theme", "sepia");

    initThemeControls(document, window);

    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
