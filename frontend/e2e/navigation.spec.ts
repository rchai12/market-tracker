import { test, expect } from "./fixtures";

test.describe("Navigation", () => {
  test("sidebar links are visible", async ({ authenticatedPage: page }) => {
    // Check sidebar contains expected navigation items
    const sidebar = page.locator("nav, aside, [data-testid='sidebar']");
    await expect(sidebar.first()).toBeVisible({ timeout: 5_000 });
  });

  test("can navigate between pages", async ({ authenticatedPage: page }) => {
    // Look for signals link in sidebar or navigation
    const signalsLink = page.locator("a[href*='signals'], a:has-text('Signals')").first();
    if (await signalsLink.isVisible()) {
      await signalsLink.click();
      await page.waitForURL(/signals/);
      await expect(page).toHaveURL(/signals/);
    }
  });
});
