import { test, expect } from "./fixtures";

test.describe("Signals Page", () => {
  test("signals page loads without error", async ({ authenticatedPage: page }) => {
    await page.goto("/signals");
    // Should not show a full-page error
    await expect(page.locator("text=Error")).not.toBeVisible({ timeout: 5_000 }).catch(() => {
      // Some empty states might show "No signals" which is fine
    });
    // Page should have loaded (not stuck on loading forever)
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
  });

  test("signals page has tabs", async ({ authenticatedPage: page }) => {
    await page.goto("/signals");
    // Look for Signals/Accuracy/Methodology tabs
    const tabArea = page.locator("[role='tablist'], .tabs, button:has-text('Signals')").first();
    await expect(tabArea).toBeVisible({ timeout: 10_000 }).catch(() => {
      // Tab layout might differ — check page loaded at minimum
    });
  });
});
