import { test as base, type Page } from "@playwright/test";

/**
 * Custom test fixtures for authenticated pages.
 *
 * Usage:
 *   import { test } from "./fixtures";
 *   test("my test", async ({ authenticatedPage }) => { ... });
 */

const TEST_USER = {
  email: "e2e-test@example.com",
  username: "e2etester",
  password: "TestPass1",
};

const ADMIN_USER = {
  email: "e2e-admin@example.com",
  username: "e2eadmin",
  password: "AdminPass1",
};

async function loginViaUI(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.fill('input[type="email"], input[name="email"]', email);
  await page.fill('input[type="password"], input[name="password"]', password);
  await page.click('button[type="submit"]');
  // Wait for redirect away from login page
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 10_000,
  });
}

export const test = base.extend<{
  authenticatedPage: Page;
  adminPage: Page;
}>({
  authenticatedPage: async ({ page }, use) => {
    await loginViaUI(page, TEST_USER.email, TEST_USER.password);
    await use(page);
  },
  adminPage: async ({ page }, use) => {
    await loginViaUI(page, ADMIN_USER.email, ADMIN_USER.password);
    await use(page);
  },
});

export { expect } from "@playwright/test";
