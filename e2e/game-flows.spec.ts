import { expect, test } from "@playwright/test";

test("theme selection persists on the landing page", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Cupertino" }).click();

  await expect(page.locator("html")).toHaveAttribute("data-theme", "cupertino");

  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "cupertino");
});

test("iteration mode can start and resolve one fake-ranked turn", async ({ page }) => {
  await page.goto("/");
  await page.locator('form[action="/start-iteration-mode"] button[type="submit"]').click();

  await expect(page).toHaveURL(/iteration-mode/);
  const targetWord = (await page.locator("#target-value").textContent())?.trim() ?? "";
  await page.locator("#clue-input").fill(targetWord);
  await page.locator("#clue-form").press("Enter");

  await expect(page.locator("#status-banner")).not.toHaveText("");
  await expect(page.locator("#provider-badge")).toContainText(/fake-ranker|local-rule-validator/);
});

test("restriction mode can start and resolve one deterministic turn", async ({ page }) => {
  await page.goto("/");
  await page.locator('form[action="/start-restriction-mode"] button[type="submit"]').click();

  await expect(page).toHaveURL(/restriction-mode/);
  const targetWord = (await page.locator("#target-value").textContent())?.trim() ?? "";
  await page.locator("#clue-input").fill(targetWord);
  await page.locator("#clue-form").press("Enter");

  await expect(page.locator("#status-banner")).not.toHaveText("");
  await expect(page.locator("#provider-badge")).toContainText(/fake-ranker|local-rule-validator/);
});

test("blocks mode can start and resolve one deterministic turn", async ({ page }) => {
  await page.goto("/");
  await page.locator('form[action="/start-blocks-mode"] button[type="submit"]').click();

  await expect(page).toHaveURL(/blocks-mode/);
  const firstWord = (
    (await page.locator(".blocks-cell--filled").first().getAttribute("data-word")) ?? ""
  ).trim();
  await page.locator("#clue-input").fill(firstWord);
  await page.locator("#clue-form").press("Enter");

  await expect(page.locator("#status-banner")).not.toHaveText("");
  await expect(page.locator("#provider-badge")).toContainText("fake-ranker");
});
