const STORAGE_KEY = "semantris-theme";

const THEME_OPTIONS = ["light", "dark", "cupertino"] as const;

type ThemeOption = (typeof THEME_OPTIONS)[number];

function isThemeOption(value: string | null): value is ThemeOption {
  return value !== null && THEME_OPTIONS.includes(value as ThemeOption);
}

function getSystemTheme(windowRef: Window = window): ThemeOption {
  return windowRef.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme(windowRef: Window = window): ThemeOption | null {
  try {
    const value = windowRef.localStorage.getItem(STORAGE_KEY);
    return isThemeOption(value) ? value : null;
  } catch {
    return null;
  }
}

function setStoredTheme(theme: ThemeOption, windowRef: Window = window): void {
  try {
    windowRef.localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Ignore storage failures and still apply the selected theme for this session.
  }
}

function resolveTheme(windowRef: Window = window): ThemeOption {
  return getStoredTheme(windowRef) ?? getSystemTheme(windowRef);
}

function applyTheme(documentRef: Document, windowRef: Window = window): ThemeOption {
  const theme = resolveTheme(windowRef);
  documentRef.documentElement.dataset.theme = theme;
  return theme;
}

function syncButtons(buttons: HTMLButtonElement[], activeTheme: ThemeOption): void {
  buttons.forEach((button) => {
    const isActive = button.dataset.themeOption === activeTheme;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

export function initThemeControls(
  documentRef: Document = document,
  windowRef: Window = window
): void {
  const buttons = Array.from(
    documentRef.querySelectorAll<HTMLButtonElement>("[data-theme-option]")
  );

  if (!buttons.length) {
    return;
  }

  const applyAndSync = (): void => {
    const activeTheme = applyTheme(documentRef, windowRef);
    syncButtons(buttons, activeTheme);
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const theme = button.dataset.themeOption ?? null;
      if (!isThemeOption(theme)) {
        return;
      }

      setStoredTheme(theme, windowRef);
      applyAndSync();
    });
  });

  const mediaQuery = windowRef.matchMedia("(prefers-color-scheme: dark)");
  const handleThemeChange = (): void => {
    if (!getStoredTheme(windowRef)) {
      applyAndSync();
    }
  };

  if (typeof mediaQuery.addEventListener === "function") {
    mediaQuery.addEventListener("change", handleThemeChange);
  } else if (typeof mediaQuery.addListener === "function") {
    mediaQuery.addListener(handleThemeChange);
  }

  applyAndSync();
}

initThemeControls();
