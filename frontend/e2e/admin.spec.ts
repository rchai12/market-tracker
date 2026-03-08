import { test, expect } from "./fixtures";

test.describe("Admin Page", () => {
  test("admin can access admin page", async ({ adminPage: page }) => {
    await page.goto("/admin");
    // Admin page should show task triggers or DB stats
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
    // Should not redirect away from admin
    await expect(page).toHaveURL(/admin/);
  });

  test("non-admin cannot access admin page", async ({ authenticatedPage: page }) => {
    await page.goto("/admin");
    // Should redirect to dashboard or show access denied
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
    // Non-admin should be redirected away from admin page
    const url = page.url();
    const isRedirected = !url.includes("/admin") || url.includes("/login");
    const hasError = await page.locator("text=permission, text=forbidden, text=denied").first().isVisible().catch(() => false);
    expect(isRedirected || hasError).toBeTruthy();
  });
});
